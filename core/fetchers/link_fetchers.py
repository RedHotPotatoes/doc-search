from typing import Any


class LinkFetcher:
    def get_link(self, document: dict[str, Any]) -> str:
        raise NotImplementedError


class StackOverflowLinkFetcher:
    def get_link(self, document: dict[str, Any]) -> str:
        doc_id = document["metadata"]["Id"]
        return f"https://stackoverflow.com/questions/{doc_id}"


class GithubIssueLinkFetcher:
    def get_link(self, document: dict[str, Any]) -> str:
        return document["metadata"]["url"]
