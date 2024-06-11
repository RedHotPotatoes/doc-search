import os
from typing import List

import logging
import pretty_logging
import requests
from pretty_logging import with_logger
from requests import Response

from core.db import Database, MongoDB
from core.rate_limits.github import FirstLimitRateMixin, PointsRateLimitMixin

handler = logging.FileHandler("fetch_all_github_repos.log")
logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@with_logger
class GitHubReposFetcher(FirstLimitRateMixin, PointsRateLimitMixin):
    URL = "https://api.github.com/repositories"
    PARAMS = {"q": "is:public", "per_page": 100, "page": 1}
    PARSE_KEYS = ["id", "name", "full_name", "private", "html_url", "fork", "url"]

    def __init__(self, db: Database, parse_keys: List[str] | None = None):
        super().__init__()
        self._db = db
        self._parse_keys = parse_keys or self.PARSE_KEYS

    def _update_data(self, data):
        insert_data = [{key: repo[key] for key in self._parse_keys} for repo in data]
        self._db.insert_bulk(insert_data)

    def _check_rate_limits(self, response: Response, request_types: List[str]):
        self.apply_first_rate_limit(response, time_delta=5.0)

        # We are unable to violate the majority of the secondary rate limits since we fetch pages sequentially:
        # We have no concurrent requests and the upper-bound for the CPU time is 60 seconds per minute.
        # The only limit that we theoretically can violate is the number of points per minute:
        self.apply_points_rate_limit(request_types, time_delta=2.0)

    def fetch_repos(self, github_token: str = None):
        self._log.info("Fetching all GitHub repositories...")
        headers = {
            "X-GitHub-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github.v3+json",
        }
        if github_token is not None:
            headers["Authorization"] = f"Bearer {github_token}"
        response = requests.get(self.URL, headers=headers, params=self.PARAMS, )
        self._check_rate_limits(response, ["get"])
        self._log.info(
            f"First rate limit: {self._queries_remaining} queries remaining."
        )
        data = response.json()
        self._update_data(data)

        page_counter = 1
        while True:
            if "next" not in response.links:
                self._log.info("Finished fetching github repositories.")
                return
            url = response.links["next"]["url"]
            self._log.info(f"Fetching next page: {url}")
            response = requests.get(url, headers=headers)
            self._check_rate_limits(response, ["get"])
            self._log.info(
                f"First rate limit: {self._queries_remaining} queries remaining."
            )
            try: 
                data = response.json()
                self._update_data(data)
            except Exception as e:
                self._log.error(f"Error occured during writing data into db: {e}")
                self._log.error(f"Response: {response.text}")

            page_counter += 1
            if page_counter % 10 == 0:
                self._log.info(f"Processed {page_counter} pages.")
        self._log.info(f"Finished processing {page_counter} pages.")

            
if __name__ == "__main__":
    pretty_logging.setup("INFO")

    mongo_host = os.getenv("MONGODB_HOST", "mongodb")
    mongo_port = os.getenv("MONGODB_PORT", 27017)
    github_token = os.getenv("GITHUB_TOKEN", None)

    host = f"mongodb://{mongo_host}:{mongo_port}/"
    db = MongoDB(
        host,
        default_db="github_crawl",
        default_collection="repositories",
        username=os.getenv("MONGODB_ADMIN_USER"),
        password=os.getenv("MONGODB_ADMIN_PASS"),
    )
    fetcher = GitHubReposFetcher(db)
    fetcher.fetch_repos(github_token)
