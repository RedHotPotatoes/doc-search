import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

from core.fetchers.fetchers import FetcherType
from core.fetchers.shallow_fetchers import ShallowFetcher
from core.processors import DocumentProcessor


class Reranker(Protocol):
    def rerank(self, documents: list[str], query: str) -> list[dict[str, Any]]: ...


@dataclass
class RetrieveSource:
    fetcher: FetcherType
    shallow_fetcher: ShallowFetcher | None
    document_processor: DocumentProcessor


class DocumentRetriever:
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
        documents = await self._documents_retrieve(documents)
        documents = self._format_documents(documents)
        return documents
