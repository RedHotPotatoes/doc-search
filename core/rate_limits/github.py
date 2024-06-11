"""
GitHub API has rate limits. More specifically, there are primary and secondary rate limits.
The primary rate limit is either 60 requests per hour for unauthenticated requests or 5000 
requests per hour for authenticated requests, or GitHub Enterprise Cloud that has a rate limit of 
15000 requests per hour.

The secondary rate limits are:
    - No more than 100 concurrent requests
    - No more than 900 points per minute (see table: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28#calculating-points-for-the-secondary-rate-limit)
    - No more than 90 seconds of CPU time per minute (roughly equivalent to the total response time 
        for all requests in a minute)
"""

import time
from collections import deque
from typing import List

from pretty_logging import with_logger
from requests import Response


@with_logger
class FirstLimitRateMixin:
    _queries_remaining: int = 0
    _reset_timestemp: int = 0

    def apply_first_rate_limit(
        self, response: Response, time_delta: float = 0.0
    ) -> None:
        self._update_first_rate_limit(response)
        if self.is_first_rate_limit_exceeded:
            time_to_wait = self.first_rate_limit_time_to_wait
            self._log.info(
                f"First rate limit exceeded. Sleeping for {time_to_wait:.2f} seconds."
            )
            time.sleep(time_to_wait + time_delta)

    def _update_first_rate_limit(self, response: Response) -> None:
        self._queries_remaining = int(response.headers["X-RateLimit-Remaining"])
        self._reset_timestemp = int(response.headers["X-RateLimit-Reset"])

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

    _points: deque = deque([])
    _timestamps: deque = deque([])
    _total_points: int = 0

    def apply_points_rate_limit(
        self, request_types: List[str], time_delta: float = 0.0
    ) -> None:
        self._update_points_rate_limit(request_types)
        if self.is_points_limit_exceeded:
            time_to_wait = self.points_limit_time_to_wait
            self._log.info(
                f"Points limit exceeded. Sleeping for {time_to_wait:.2f} seconds."
            )
            time.sleep(time_to_wait + time_delta)

    def _update_points_rate_limit(self, request_types: List[str]) -> None:
        points = sum(
            self.POINTS_MAPPING[request_type] for request_type in request_types
        )
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
