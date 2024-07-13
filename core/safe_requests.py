import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict

import requests
from pretty_logging import with_logger
from requests import Response

_log = logging.getLogger(Path(__file__).stem)


def _safe_request(
    request_func: Callable,
    handle_func: Callable,
    url: str,
    headers: Dict[str, str] | None = None,
    params: Dict[str, str] | None = None,
    proxies: Dict[str, str] | None = None,
    max_retries: int = 5,
    retry_delay: float = 5.0,
    **request_kwargs
):
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = request_func(
                url, headers=headers, params=params, proxies=proxies, **request_kwargs
            )
            result = handle_func(response, url, headers, params)
            break
        except Exception as e:
            _log.error(f"Error occured during fetching data: {e}")
            _log.info(f"Retrying... {retry_count + 1}/{max_retries}")
            _log.info(f"Retrying in {retry_delay} seconds.")

            retry_count += 1
            time.sleep(retry_delay)
    else:
        _log.error(f"Failed to fetch url: {url} after {max_retries} retries.")
        return
    return result


@with_logger
class SafeRequestMixin:
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
        return _safe_request(
            self._client.get,
            self._handle_get_response,
            url,
            headers,
            params,
            proxies,
            self._max_retries,
            self._retry_delay,
        )

    def _post_request(
        self,
        url: str,
        data: dict | None = None,
        json: dict | None = None,
        headers: Dict[str, str] | None = None,
        params: Dict[str, str] | None = None,
        proxies: Dict[str, str] | None = None,
    ):
        return _safe_request(
            self._client.post,
            self._handle_post_response,
            url,
            headers,
            params,
            proxies,
            self._max_retries,
            self._retry_delay,
            data=data,
            json=json,
        )

    def _handle_get_response(
        self,
        response: Response,
        url: str | None,
        headers: Dict[str, str] | None,
        params: Dict[str, str] | None,
    ) -> Any:
        raise NotImplementedError

    def _handle_post_response(
        self,
        response: Response,
        url: str | None,
        headers: Dict[str, str] | None,
        params: Dict[str, str] | None,
    ) -> Any:
        raise NotImplementedError
