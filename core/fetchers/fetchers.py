import asyncio
from pydoc import doc
from typing import Any

import aiohttp
from requests import Response

from core.parsers.github import parse_github_issue_page
from core.safe_requests_async import SafeRequestMixin
from core.data_structures import GithubIssueDocument


class Fetcher:
    async def fetch_full(self, shallow_fetch_data: list[dict[str, Any]]) -> Any:
        raise NotImplementedError


class GitHubIssuesFetcher(Fetcher, SafeRequestMixin):
    async def fetch_full(self, shallow_fetch_data: list[dict[str, Any]]) -> list[GithubIssueDocument | None]:
        links = [item["url"] for item in shallow_fetch_data]

        async with aiohttp.ClientSession() as client:
            documents = await asyncio.gather(*[self._get_request(client, link) for link in links])
        return [self._maybe_parse_document(doc) for doc in documents]
    
    def _maybe_parse_document(self, document) -> GithubIssueDocument | None:
        if document is not None:
            return parse_github_issue_page(document)
        return 

    async def _handle_get_response(
        self,
        response: Response,
        url: str | None,
        headers: dict[str, str] | None,
        params: dict[str, str] | None,
    ) -> Any:
        response.raise_for_status()
        return await response.text()
