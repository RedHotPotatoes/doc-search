import time
from collections import deque
from typing import Any, List, Protocol, Dict

import pretty_logging
import requests
from pretty_logging import with_logger
from requests import Response
from pymongo import MongoClient


class Database(Protocol):
    def get(self, key: str) -> Any:
        ...

    def insert(self, key: str, value: Any) -> None:
        ...

    def insert_bulk(self, data: dict[str, Any]) -> None:
        ...


class MongoDB:
    def __init__(self, uri: str, default_db: str, default_collection: str):
        self._client = MongoClient(uri)
        self._default_db = self._client[default_db]
        self._default_collection = self._default_db[default_collection]

    def __del__(self):
        self._client.close()
        
    def get(self, key: str, database: str | None = None, collection: str | None = None) -> Any:
        collection = self._get_collection(database, collection)
        return collection.find_one({"_id": key}) or {}

    def insert(self, data: Dict[str, Any], database: str | None = None, collection: str | None = None) -> None:
        collection = self._get_collection(database, collection)
        collection.insert_one(data)

    def insert_bulk(self, data: List[Dict[str, Any]], database: str | None = None, collection: str | None = None) -> None:
        collection = self._get_collection(database, collection)
        collection.insert_many(data)

    def _get_collection(self, database: str | None = None, collection: str | None = None) -> Any:
        if collection is None:
            return self._default_collection
        if database is None:
            return self._default_db[collection]
        return self._client[database][collection]


@with_logger
class FirstLimitRateMixin:
    def apply_first_rate_limit(self, response: Response, time_delta: float = 0.0) -> None:
        self._update_first_rate_limit(response)
        if self.is_first_rate_limit_exceeded:
            time_to_wait = self.first_rate_limit_time_to_wait
            self._log.info(f"First rate limit exceeded. Sleeping for {time_to_wait:.2f} seconds.")
            time.sleep(time_to_wait + time_delta)

    def _update_first_rate_limit(self, response: Response) -> None:
        self._queries_remaining = response.headers["X-RateLimit-Remaining"]
        self._reset_timestemp = response.headers["X-RateLimit-Reset"]

    @property 
    def is_first_rate_limit_exceeded(self) -> bool:
        return self._queries_remaining == 0
    
    @property
    def first_rate_limit_time_to_wait(self) -> float:
        return int(self._reset_timestemp) - time.time()
        

@with_logger
class PointsRateLimitMixin:
    POINTS_RATE_LIMIT = 900
    POINTS_MAPPING = {
        "get": 1,
        "head": 1,
        "options": 1,
        "post": 5,
        "patch": 5,
        "put": 5,
        "delete": 5,
    }

    def __init__(self):
        self._points = deque([])
        self._timestamps = deque([])
        self._total_points = 0

    def apply_points_rate_limit(self, request_types: List[str], time_delta: float = 0.0) -> None:
        self._update_points_rate_limit(request_types)
        if self.is_points_limit_exceeded:
            time_to_wait = self.points_limit_time_to_wait
            self._log.info(f"Points limit exceeded. Sleeping for {time_to_wait:.2f} seconds.")
            time.sleep(time_to_wait + time_delta)

    def _update_points_rate_limit(self, request_types: List[str]) -> None:
        points = sum(self.POINTS_MAPPING[request_type] for request_type in request_types)
        curr_time = time.time()
        self._points.append(points)
        self._timestamps.append(curr_time)
        self._total_points += points

        while curr_time - self._timestamps[0] > 60:
            self._total_points -= self._points.popleft()
            self._timestamps.popleft()

    @property
    def is_points_limit_exceeded(self) -> bool:
        return self._total_points > self.POINTS_RATE_LIMIT
    
    @property
    def points_limit_time_to_wait(self) -> float:
        return 60 - (time.time() - self._timestamps[0])


@with_logger
class GitHubReposFetcher(FirstLimitRateMixin, PointsRateLimitMixin):
    URL = "https://api.github.com/repositories"
    PARAMS = {"q": "is:public", "per_page": 100, "page": 1}
    PARSE_KEYS = ["id", "name", "full_name", "private", "html_url", "fork", "url"]

    def __init__(self, db: Database, parse_keys: List[str] | None = None):
        super().__init__()
        self._db = db
        self._parse_keys = parse_keys or self.PARSE_KEYS

        self._points = []
        self._timestamps = [] 
        self._total_points = 0

    def _update_data(self, data):
        insert_data = [
            {key: repo[key] for key in self._parse_keys} for repo in data
        ]
        self._db.insert_bulk(insert_data)

    def _check_rate_limits(self, response: Response, request_types: List[str]):
        """GitHub API has rate limits. More specifically, there are primary and secondary rate limits.
        The primary rate limit is either 60 requests per hour for unauthenticated requests or 5000 requests per hour for authenticated requests,
        or GitHub Enterprise Cloud that has a rate limit of 15000 requests per hour.

        The secondary rate limits are:
         - No more than 100 concurrent requests 
         - No more than 900 points per minute (see table: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28#calculating-points-for-the-secondary-rate-limit)
         - No more than 90 seconds of CPU time per minute (roughly equivalent to the total response time for all requests in a minute)        

        Args:
            response (Response): requests Response object
        """
        self.apply_first_rate_limit(response, time_delta=5.0)

        # We are unable to violate the majority of the secondary rate limits since we fetch pages sequentially:
        # We have no concurrent requests and the upper-bound for the CPU time is 60 seconds per minute.
        # The only limit that we theoretically can violate is the number of points per minute:
        self.apply_points_rate_limit(request_types, time_delta=2.0)
        
    def fetch_repos(self):
        self._log.info("Fetching all GitHub repositories...")
        response = requests.get(self.URL, params=self.PARAMS)
        data = response.json()
        self._update_data(data)

        while True:
            if "next" not in response.links:
                return 
            self._check_rate_limits(response, ["get"])
            url = response.links["next"]["url"]
            response = requests.get(url)
            data = response.json()
            self._update_data(data)


if __name__ == "__main__":
    pretty_logging.setup("INFO")
    fetcher = GitHubReposFetcher("db.json")
    fetcher.fetch_repos()
