from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

import aiohttp
from pretty_logging import with_logger
from requests import Response

from core.fetchers.fetchers import FetcherType, WebPageFetcher
from core.fetchers.link_fetchers import LinkFetcher
from core.fetchers.shallow_fetchers import ShallowFetcher
from core.parsers import get_parser
from core.processors import DocumentProcessor
from core.safe_requests_async import SafeRequestMixin


class Reranker(Protocol):
    def rerank(self, documents: list[str], query: str) -> list[dict[str, Any]]: ...


class SearchEngine(Protocol):
    async def search(self, query: str) -> list[str]: ...


class DocumentRetriever(Protocol):
    async def retrieve_documents(self, query: str) -> Any: ...


@dataclass
class RetrieveSource:
    fetcher: FetcherType
    shallow_fetcher: ShallowFetcher
    link_fetcher: LinkFetcher
    document_processor: DocumentProcessor


class MixedSourceDocumentRetriever:
    def __init__(self, sources: dict[str, RetrieveSource], reranker: Reranker):
        self._sources = sources
        self._reranker = reranker

    async def _initial_documents_retrieve(
        self, query: str
    ) -> list[tuple[str, dict[str, Any]]]:
        documents = []
        for source, source_data in self._sources.items():
            fetcher = source_data.fetcher
            shallow_fetcher = source_data.shallow_fetcher

            if shallow_fetcher:
                docs = shallow_fetcher.fetch(query)
            else:
                docs = await fetcher.fetch_documents(query)
            documents.extend((source, doc) for doc in docs)
        return documents

    async def _documents_retrieve(
        self, documents: list[tuple[str, dict[str, Any]]]
    ) -> list[tuple[str, dict[str, Any]]]:
        documents_dict = defaultdict(list)
        for source, doc in documents:
            documents_dict[source].append(doc)

        retrieve_result = {}

        # TODO: await on whole list of documents
        for source, document_list in documents_dict.items():
            fetcher = self._sources[source].fetcher
            shallow_fetcher = self._sources[source].shallow_fetcher

            if not shallow_fetcher:
                retrieve_result[source] = document_list
            else:
                retrieve_result[source] = await fetcher.fetch_documents(document_list)
        return retrieve_result

    def _prepare_rerank_documents(
        self, documents: list[tuple[str, dict[str, Any]]]
    ) -> list[str]:
        rerank_documents = []
        for _, doc in documents:
            rerank_documents.append(". ".join([doc["title"], doc["body"]]))
        return rerank_documents

    def _prepare_rerank_query(self, query: str, description: str) -> str:
        if description:
            return ". ".join([query, description])
        return query

    def _rerank_documents(
        self, documents: list[str], query: str, description: str
    ) -> list[dict[str, Any]]:
        rerank_documents = self._prepare_rerank_documents(documents)
        rerank_query = self._prepare_rerank_query(query, description)
        rerank_result = self._reranker.rerank(rerank_documents, rerank_query)

        indices = [result["index"] for result in rerank_result]
        return [documents[i] for i in indices]
    
    def _get_links(self, documents: list[dict[str, Any]]) -> list[str]:
        return [
            self._sources[source].link_fetcher.get_link(doc) for source, doc in documents
        ]

    def _format_documents(
        self, documents: dict[str, list[dict[str, Any]]]
    ) -> dict[str, list[dict[str, Any]]]:
        formatted_documents = {}
        for source, docs in documents.items():
            document_processor = self._sources[source].document_processor
            formatted_documents[source] = [
                document_processor.process(doc) for doc in docs
            ]
        return formatted_documents

    async def retrieve_documents(self, query: str, description: str):
        documents = await self._initial_documents_retrieve(query)
        documents = self._rerank_documents(documents, query, description)
        links = self._get_links(documents)
        documents = await self._documents_retrieve(documents)
        documents = self._format_documents(documents)
        return documents, links


class GoogleSearchEngine(SafeRequestMixin):
    def __init__(self, api_key: str, cse_id: str, max_results: int = 10):
        self._api_key = api_key
        self._cse_id = cse_id
        self._max_results = max_results

    async def search(self, query: str) -> list[str]:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self._api_key,
            "cx": self._cse_id,
            "q": query,
            "num": self._max_results,
        }
        async with aiohttp.ClientSession() as client:
            search_results = await self._get_request(client, url, params=params)

        links = []
        for item in search_results.get("items", []):
            links.append(item["link"])
        return links
    
    async def _handle_get_response(
        self,
        response: Response,
        url: str | None,
        headers: dict[str, str] | None,
        params: dict[str, str] | None,
    ):
        response.raise_for_status()
        return await response.json()
    

@with_logger
class WebDocumentRetriever:
    def __init__(self, search_engine: SearchEngine):
        self._search_engine = search_engine
        self._fetcher = WebPageFetcher()

    async def _parse_documents(self, links_raw: list[str]) -> Any:
        links, parsers = [], []
        for link in links_raw:
            parser = get_parser(link)
            if parser:
                links.append(link)
                parsers.append(parser)
        if not links:
            return [], {}

        documents_raw = await self._fetcher.fetch_documents(links)
        documents = []
        links_succeeded = []
        for link, parser, doc_raw in zip(links, parsers, documents_raw):
            try:
                document = parser(doc_raw)
            except Exception as e:
                self._log.error(f"Error parsing web document with link: {link}")
                self._log.error(f"Error: {e}")
                continue
            documents.append(document)
            links_succeeded.append(link)
        links_dict = {
            "links_raw": links_raw, 
            "links": links,
            "links_succeeded": links_succeeded,
        }
        return documents, links_dict

    async def retrieve_documents(self, query: str) -> Any:
        links = await self._search_engine.search(query)
        documents, links_dict = await self._parse_documents(links)
        return documents, links_dict
