import asyncio
from typing import Any

import aiohttp
from markdownify import markdownify
from qdrant_client import QdrantClient, models
from requests import Response

from core.safe_requests_async import SafeRequestMixin


class FetcherAsync:
    async def fetch_documents(self, query: Any) -> list[dict[str, Any]]:
        raise NotImplementedError


class StackOverflowFetcher(FetcherAsync):
    _embed_model_mapping = {"fast-bge-small-en-v1.5": "BAAI/bge-small-en-v1.5"}

    def __init__(
        self,
        host: str | None = None,
        api_key: str | None = None,
        collection_name: str = "stackoverflow_question_pages",
        top_k: int = 10,
        min_num_answers: int | None = None,
    ):
        # TODO: switch to async client and async api
        self._client = QdrantClient(host=host, api_key=api_key, https=False, prefer_grpc=True)
        self._collection_name = collection_name

        self._set_embed_model()

        self._top_k = top_k
        self._query_filter = self._get_query_filter(min_num_answers)

    async def fetch_documents(self, query_text: str, mardownify_body: bool = True) -> list[dict[str, Any]]:
        documents = self._client.query(
            query_text=query_text,
            collection_name=self._collection_name,
            query_filter=self._query_filter,
            limit=self._top_k,
        )
        result = []
        for doc in documents:
            document = doc.metadata
            title = document["Title"]
            body = document["Body"]
            if mardownify_body:
                body = markdownify(body, heading_style="ATX")
            result.append({"title": title, "body": body, "metadata": document})
        return result

    def _set_embed_model(self) -> None:
        collection_info = self._client.get_collection(
            collection_name=self._collection_name
        )
        embedding_models = list(collection_info.config.params.vectors.keys())

        if len(embedding_models) == 0:
            raise ValueError("No embedding models found in the collection.")
        if len(embedding_models) > 1:
            raise ValueError("Multiple embedding models found in the collection.")
        embedding_model = embedding_models[0]
        if embedding_model not in self._embed_model_mapping:
            raise KeyError(f"Unknown embedding model: {embedding_model}.")
        self._client.set_model(self._embed_model_mapping[embedding_model])

    def _get_query_filter(
        self, min_num_answers: int | None
    ) -> models.Filter | None:
        filters = []
        if min_num_answers:
            filters.append(
                models.FieldCondition(
                    key="num_answers",
                    range=models.Range(gte=min_num_answers),
                )
            )
        if filters:
            return models.Filter(must=filters)
        return


class GitHubIssuesFetcher(FetcherAsync, SafeRequestMixin):
    def __init__(self, field: str = "metadata", url_field : str = "url", filter_none: bool = True):
        self._field = field
        self._url_field = url_field
        self._filter_none = filter_none

    async def fetch_documents(
        self, documents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        links = [doc[self._field][self._url_field] for doc in documents]
        
        async with aiohttp.ClientSession() as client:
            documents = await asyncio.gather(
                *[self._get_request(client, link) for link in links]
            )
        if self._filter_none:
            documents = [doc for doc in documents if doc is not None]
        return documents

    async def _handle_get_response(
        self,
        response: Response,
        url: str | None,
        headers: dict[str, str] | None,
        params: dict[str, str] | None,
    ) -> Any:
        response.raise_for_status()
        return await response.text()


FetcherType = FetcherAsync
