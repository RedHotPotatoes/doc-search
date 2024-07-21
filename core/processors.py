from typing import Any

from core.data_structures import GithubIssueDocument, StackOverflowDocument
from core.parsers.github import parse_github_issue_page
from core.parsers.stackoverflow import parse_stackoverflow_question_page


class DocumentProcessor:
    def process(self, document: Any) -> Any:
        raise NotImplementedError
    

class GithubIssueHTMLParser(DocumentProcessor):
    def process(self, html_document: str) -> GithubIssueDocument:
        return parse_github_issue_page(html_document)
    

class StackOverflowPayloadParser(DocumentProcessor):
    def __init__(self, field: str | None = "metadata") -> None:
        self._field = field

    def process(self, payload: dict[str, Any]) -> StackOverflowDocument:
        if self._field:
            return parse_stackoverflow_question_page(payload[self._field])
        return parse_stackoverflow_question_page(payload)
