import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict

import aiohttp
from pretty_logging import with_logger
from requests import Response

_log = logging.getLogger(Path(__file__).stem)


async def _safe_request(
    request_func: Callable,
    handle_func: Callable,
    url: str,
    headers: Dict[str, str] | None = None,
    params: Dict[str, str] | None = None,
    max_retries: int = 5,
    retry_delay: float = 5.0,
    **request_kwargs
):
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = await request_func(
                url, headers=headers, params=params, **request_kwargs
            )
            result = await handle_func(response, url, headers, params)
            break
        except Exception as e:
            _log.error(f"Error occured during fetching data: {e}")
            _log.info(f"Retrying... {retry_count + 1}/{max_retries}")
            _log.info(f"Retrying in {retry_delay} seconds.")

            retry_count += 1
            await asyncio.sleep(retry_delay)
    else:
        _log.error(f"Failed to fetch url: {url} after {max_retries} retries.")
        return
    return result


@with_logger
class SafeRequestMixin:
    _max_retries: int = 5
    _retry_delay: float = 5.0

    async def _get_request(
        self,
        client,
        url: str,
        headers: Dict[str, str] | None = None,
        params: Dict[str, str] | None = None,
    ):
        return await _safe_request(
            client.get,
            self._handle_get_response,
            url,
            headers,
            params,
            self._max_retries,
            self._retry_delay,
        )

    def _handle_get_response(
        self,
        response: Response,
        url: str | None,
        headers: Dict[str, str] | None,
        params: Dict[str, str] | None,
    ) -> Any:
        raise NotImplementedError
