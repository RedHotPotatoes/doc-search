from typing import Dict, Any
import time
from pretty_logging import with_logger
import requests
from requests import Response


@with_logger
class GetRequestMixin:
    _max_retries: int = 5
    _retry_delay: float = 5.0
    _client = requests.Session()

    def _get_request(
        self,
        url: str,
        headers: Dict[str, str] | None = None,
        params: Dict[str, str] | None = None,
        proxies: Dict[str, str] | None = None,
    ):
        retry_count = 0
        while retry_count < self._max_retries:
            try:
                response = self._client.get(url, headers=headers, params=params, proxies=proxies)
                result = self._handle_response(response, url, headers, params)
                break
            except Exception as e:
                self._log.error(f"Error occured during fetching data: {e}")
                self._log.info(f"Retrying... {retry_count + 1}/{self._max_retries}")
                self._log.info(f"Retrying in {self._retry_delay} seconds.")

                retry_count += 1
                time.sleep(self._retry_delay)
        else:
            self._log.error(
                f"Failed to fetch url: {url} after {self._max_retries} retries."
            )
            return
        return result

    def _handle_response(
        self,
        response: Response,
        url: str | None,
        headers: Dict[str, str] | None,
        params: Dict[str, str] | None,
    ) -> Any:
        raise NotImplementedError
