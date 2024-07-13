from typing import Any, Dict
import requests
from qdrant_client import QdrantClient
from core.safe_requests import SafeRequestMixin
from core.status_codes import HttpStatusCode
from pretty_logging import with_logger


class ShallowFetcher:
    def fetch(self, query: str, query_description: str) -> Any:
        raise NotImplementedError


class StackOverflowShallowFetcher:
    def __init__(
        self,
        host: str | None = None,
        api_key: str | None = None,
        collection_name: str = "stackoverflow",
        top_k: int = 10,
    ):
        self._client = QdrantClient(host=host, api_key=api_key)
        self._collection_name = collection_name
        self._top_k = top_k

    def fetch(self, text: str) -> Any:
        response = self._client.search(
            query=text, collection_name=self._collection_name, top_k=self._top_k
        )
        return response


@with_logger
class GithubIssuesShallowFetcher(SafeRequestMixin):
    _fetch_keys = ["title", "url", "bodyHTML"]
    _keys_mapping = {
        "title": "title",
        "url": "url",
        "bodyHTML": "body",
        "createdAt": "created_at",
        "state": "state",
    }

    # TODO: add rate limits
    def __init__(self, github_token: str | None = None, top_k: int = 10):
        headers = {
            "X-GitHub-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github.v3+json",
        }
        if github_token is not None:
            headers["Authorization"] = f"Bearer {github_token}"
        self._headers = headers
        self._url = "https://api.github.com/graphql"
        self._top_k = top_k

    def fetch(self, query_text: str, query_description: str = None) -> Any:
        query = """
{
  search(query: "%s", type: ISSUE, first: %d) {
    edges {
      node {
        ... on Issue {
          title
          url
          state
          createdAt
          bodyHTML
        }
      }
    }
  }
}
""" % (
            query_text,
            self._top_k,
        )
        response = self._post_request(
            self._url, json={"query": query}, headers=self._headers
        )
        documents = []
        for edge in response["data"]["search"]["edges"]:
            node = edge["node"]
            if self._check_keys(node):
                documents.append(
                    {self._keys_mapping[key]: node[key] for key in self._fetch_keys}
                )
        return documents

    def _check_keys(self, node: Dict[str, Any]) -> bool:
        for key in self._fetch_keys:
            if key not in node:
                return False
        return True

    def _handle_post_response(
        self,
        response: requests.Response,
        url: str | None,
        headers: Dict[str, str] | None,
        params: Dict[str, str] | None,
    ) -> Any:
        if int(response.status_code) != HttpStatusCode.OK.value:
            self._log.error(
                f"Failed to fetch url: {url}. Status code: {response.status_code}."
            )
            if int(response.status_code) == HttpStatusCode.FORBIDDEN.value:
                self._log.error(f"Forbidden. Reason: {response.reason}.")
            raise Exception("Bad status code.")

        result = response.json()
        if "data" not in result:
            raise KeyError("Invalid response data. Missing 'data' key.")
        if "search" not in result["data"]:
            raise KeyError("Invalid response data. Missing 'search' key.")
        if "edges" not in result["data"]["search"]:
            raise KeyError("Invalid response data. Missing 'edges' key.")
        return result
