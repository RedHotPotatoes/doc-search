import logging
import os
import time
from copy import copy
from typing import Any, Dict, List

import numpy as np
import pretty_logging
import requests
from pretty_logging import with_logger

from core.db import Database, MongoDB
from core.safe_requests import GetRequestMixin
from core.status_codes import HttpStatusCode

handler = logging.FileHandler("fetch_all_stackoverflow_question.log")
logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

DAY_IN_SEC = 86400.0
EXTRA_WAIT_TIME_IN_SEC = 10.0
BACKOFF_EXTRA_WAIT_TIME_IN_SEC = 2.0

@with_logger
class Worker(GetRequestMixin):
    def __init__(
        self, 
        app_key: str | None = None, 
        proxy_address: str | None = None, 
        proxy_user: str | None = None, 
        proxy_password: str | None = None,  
        parse_keys: List[str] | None = None
    ):
        self._init_time = None
        self._restart_time = None
        self._quota_remaining = None
        self._backoff_end_time = None

        self._app_key = app_key
        self._parse_keys = parse_keys

        self._proxies = None
        if proxy_address is not None:
            proxy_login = ""
            if proxy_user is not None:
                proxy_login = f"{proxy_user}:{proxy_password}@"
            self._proxies = {
                "http": f"http://{proxy_login}{proxy_address}",
                "https": f"http://{proxy_login}{proxy_address}"
            }

    @property
    def init_time(self):
        return self._init_time

    @property
    def restart_time(self):
        return self._restart_time

    @property
    def backoff_end_time(self):
        return self._backoff_end_time

    @property
    def quota_remaining(self):
        return self._quota_remaining
    
    @property
    def parse_keys(self):
        return self._parse_keys
    
    @parse_keys.setter
    def parse_keys(self, parse_keys: List[str]):
        if self._parse_keys is not None:
            self._log.warning("Overwriting parse keys.")
        self._parse_keys = parse_keys

    def get_request(self, url: str, params: Dict[str, Any]):
        if self._init_time is None:
            self._init_start_time()
        if self._app_key is not None:
            params["key"] = self._app_key
        response = self._get_request(url, params=params, proxies=self._proxies)
        if response is None:
            return
        response, data = response
        meta = {key: data[key] for key in ["has_more", "quota_max", "quota_remaining"]}
        self._quota_remaining = meta["quota_remaining"]
        return response, data, meta

    def _handle_response(
        self,
        response: requests.Response,
        url: str | None,
        headers: Dict[str, str] | None,
        params: Dict[str, str] | None,
    ) -> Any:
        if int(response.status_code) != HttpStatusCode.OK.value:
            self._log.error(
                f"Failed to fetch url: {url}. Status code: {response.status_code}."
            )
            self._log.error(
                f"Failed to fetch url: {url}. Reason: {response.reason}."
            )
            if int(response.status_code) == HttpStatusCode.FORBIDDEN.value:
                self._log.error(f"Forbidden. Reason: {response.reason}.")
                self._quota_remaining = 0
            raise Exception("Bad status code.")
        data = response.json()
        self._validate_response_data(data)
        return response, data
    
    def _validate_response_data(self, data):
        for item in data["items"]:
            if not all(key in item for key in self._parse_keys):
                raise ValueError("Invalid response data.")

    def _init_start_time(self):
        self._init_time = time.time()
        self._restart_time = self._init_time + DAY_IN_SEC + EXTRA_WAIT_TIME_IN_SEC

    def reset_worker(self, url: str, params: Dict[str, Any]):
        self._init_time = None
        self._restart_time = None
        self._quota_remaining = None
        self.get_request(url, params)

    def reset_backoff_time(self):
        self._backoff_end_time = None

    def set_backoff_time(self, backoff_time: int):
        self._backoff_end_time = time.time() + backoff_time + BACKOFF_EXTRA_WAIT_TIME_IN_SEC


@with_logger
class StackOverflowQuestionsFetcher:
    URL = "https://api.stackexchange.com/2.3/questions"
    PARAMS = {
        "order": "desc",
        "sort": "creation",
        "site": "stackoverflow",
        "filter": "withbody",
        "pagesize": 100,
        "page": 1,
    }
    PARSE_KEYS = [
        "question_id",
        "title",
        "body",
        "link",
        "tags",
        "is_answered",
        "view_count",
        "answer_count",
        "score",
        "creation_date",
        "last_activity_date",   
    ]
    INDEX_KEY = "question_id"

    def __init__(
        self,
        db: Database,
        workers: List[Worker],
        log_every_n_pages: int = 100,
        parse_keys: List[str] | None = None,
    ) -> None:
        self._db = db
        self._parse_keys = parse_keys or self.PARSE_KEYS
        self._log_every_n_pages = log_every_n_pages
        self._workers = workers

        for worker in self._workers:
            worker.parse_keys = self._parse_keys

    @property
    def _workers_quotas(self) -> List[int]:
        return [worker.quota_remaining for worker in self._workers]

    @property
    def _workers_start_times(self) -> List[float]:
        return [worker.init_time for worker in self._workers]

    def fetch_questions(self, verbose: bool = False) -> None:
        self._log.info("Fetching all StackOverflow question links...")

        self._init_run()
        self._log.info(
            f"Fetching on {len(self._workers)} workers. "
            f"Remainig quotas for the next 24 hours are {self._workers_quotas}"
        )
        params = copy(self.PARAMS)
        while True:
            self._maybe_reset_workers()
            id_ = self._sample_worker_id()
            if id_ is None:
                self._wait_for_next_request()
                continue

            result = self._workers[id_].get_request(self.URL, params)
            if result is None:
                self._log.error(f"Failed to parse stackoverflow question links")
                self._log.warning(f"Interrupting fetching process. Latest page: {params['page']}")                
                return
            _, data, meta = result
            if "backoff" in data:
                self._log.warning(f"Backoff: {data['backoff']} seconds.")
                self._workers[id_].set_backoff_time(data["backoff"])

            self._update_db_with_response_data(data)
            if not meta["has_more"]:
                self._log.info(f"Finished to parse stackoverflow question links...")
                return
            params["page"] += 1
            if verbose and params["page"] % self._log_every_n_pages == 0:
                self._log.info(f"Processed {params['page']} pages.")
                self._log.info(
                    f"Quotas remaining per worker: {self._workers_quotas}"
                )

    def _sample_worker_id(self) -> int | None:
        quotas = self._workers_quotas
        for index, worker in enumerate(self._workers):
            if worker.backoff_end_time is not None:
                quotas[index] = 0
        if not any(quotas):
            self._log.info("All workers are either in backoff or out of quota.")
            return
        probs = np.array(quotas) / np.sum(quotas)
        return np.random.choice(np.arange(len(quotas)), size=1, p=probs)[0]

    def _init_run(self) -> None:
        for worker in self._workers:
            worker.get_request(self.URL, self.PARAMS)

    def _maybe_reset_workers(self):
        for index, worker in enumerate(self._workers):
            if worker.restart_time is not None and worker.restart_time < time.time():
                self._log.info(f"Resetting worker {index}...")
                worker.reset_worker(self.URL, self.PARAMS)

            if worker.backoff_end_time is not None and worker.backoff_end_time < time.time():
                self._log.info(f"Resetting backoff time for worker {index}...")
                worker.reset_backoff_time()
            
    def _wait_for_next_request(self) -> None:
        cur_time = time.time()
        wait_times = []
        for worker in self._workers:
            if worker.quota_remaining == 0:
                w_time = max(0, worker.restart_time - cur_time, worker.backoff_end_time or 0 - cur_time)
            else:
                w_time = max(0, worker.backoff_end_time or 0 - cur_time)
            wait_times.append(w_time)
        
        wait_time = min(wait_times)
        self._log.info(f"Sleeping for {wait_time} seconds...")
        time.sleep(wait_time)

    def _update_db_with_response_data(self, data: Dict[str, Any]):
        insert_data = [{key: item[key] for key in self._parse_keys} for item in data["items"]]
        self._db.update_bulk(self.INDEX_KEY, insert_data, upsert=True)


if __name__ == "__main__":
    pretty_logging.setup("INFO")

    mongo_host = os.getenv("MONGODB_HOST", "mongodb")
    mongo_port = os.getenv("MONGODB_PORT", 27017)

    app_key1 = os.getenv("STACKOVERFLOW_APP_KEY1")
    app_key2 = os.getenv("STACKOVERFLOW_APP_KEY2")
    app_key3 = os.getenv("STACKOVERFLOW_APP_KEY3")

    proxy_user = os.getenv("PROXY_USER")
    proxy_password = os.getenv("PROXY_PASSWORD")
    proxy_address1 = os.getenv("PROXY_ADDRESS1")
    proxy_address2 = os.getenv("PROXY_ADDRESS2")
    proxy_address3 = os.getenv("PROXY_ADDRESS3")

    host = f"mongodb://{mongo_host}:{mongo_port}/"
    db = MongoDB(
        host,
        default_db="stackoverflow_crawl",
        default_collection="questions",
        username=os.getenv("MONGODB_ADMIN_USER"),
        password=os.getenv("MONGODB_ADMIN_PASS"),
    )
    workers = [
        Worker(app_key1, proxy_address1, proxy_user, proxy_password),
        Worker(app_key2, proxy_address2, proxy_user, proxy_password),
        Worker(app_key3, proxy_address3, proxy_user, proxy_password),
    ]
    fetcher = StackOverflowQuestionsFetcher(db, workers=workers)
    fetcher.fetch_questions(verbose=True)
