from typing import Any, Dict

import requests
from markdownify import markdownify
from pretty_logging import with_logger

from core.safe_requests import SafeRequestMixin
from core.status_codes import HttpStatusCode


class ShallowFetcher:
    def fetch(self, query: str) -> list[dict[str, Any]]:
        raise NotImplementedError


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
    def __init__(
        self,
        github_token: str | None = None,
        top_k: int = 10,
        min_num_comments: int = 1,
    ):
        headers = {
            "X-GitHub-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github.v3+json",
        }
        if github_token is not None:
            headers["Authorization"] = f"Bearer {github_token}"
        self._headers = headers
        self._url = "https://api.github.com/graphql"
        self._top_k = top_k
        self._min_num_comments = min_num_comments

    def fetch(self, query_text: str, markdownify_body: bool = True) -> list[dict[str, Any]]:
        query_text = query_text.replace('"', '\\"')
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
          comments {
            totalCount
          }
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
        if response is None:
            return []
        
        documents = []
        edges = response["data"]["search"]["edges"]
        for edge in edges:
            node = edge["node"]
            if self._check_keys(node) and self._check_comments_count(node):
                data = self._process_node(node, markdownify_body)
                documents.append(data)
        return documents
    
    def _process_node(self, node: Dict[str, Any], markdownify_body: bool) -> Dict[str, Any]:
        data = {self._keys_mapping[key]: node[key] for key in self._fetch_keys}
        if markdownify_body and "body" in data:
            data["body"] = markdownify(data["body"], heading_style="ATX")

        misc_keys = [key for key in data.keys() if key not in ["title", "body"]]
        data["metadata"] = {key: data.pop(key) for key in misc_keys}
        return data

    def _check_keys(self, node: Dict[str, Any]) -> bool:
        for key in self._fetch_keys:
            if key not in node:
                return False
        return True

    def _check_comments_count(self, node: Dict[str, Any]) -> bool:
        return node["comments"]["totalCount"] >= self._min_num_comments

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
