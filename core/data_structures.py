from dataclasses import dataclass
from typing import List, Protocol


class Data(Protocol): ...


@dataclass
class PlainText:
    text: str


@dataclass
class CodeBlock:
    text: str
    language: str | None


@dataclass
class Table:
    headers: List[str]
    rows: List[List[str]]


@dataclass
class Image:
    link: str
    alt_text: str


@dataclass
class Comment:
    text: str
    username: str


@dataclass
class Lists:
    items: List[str]


@dataclass
class StackOverflowQuestion:
    username: str
    question: List[Data]
    comments: List[Comment]
    tags: List[str]


@dataclass
class StackOverflowAnswer:
    username: str
    answer: List[Data]
    votes: int
    comments: List[str]


@dataclass
class StackOverflowDocument:
    title: str
    question: StackOverflowQuestion
    answers: List[StackOverflowAnswer]


class MarkdownSerializable:
    def to_markdown(self) -> str:
        raise NotImplementedError


class JsonSerializable:
    def to_json(self) -> str:
        raise NotImplementedError


@dataclass
class GithubIssueComment:
    author: str
    text: str
    reactions: dict[str, int]
    timestamp: str


@dataclass
class GithubIssueDocument(MarkdownSerializable, JsonSerializable):
    title: str
    question: GithubIssueComment
    answers: List[GithubIssueComment]

    def to_json(self) -> str:
        return {
            "title": self.title,
            "question": {
                "author": self.question.author,
                "text": self.question.text,
                "reactions": self.question.reactions,
                "timestamp": self.question.timestamp,
            },
            "answers": [
                {
                    "author": answer.author,
                    "text": answer.text,
                    "reactions": answer.reactions,
                    "timestamp": answer.timestamp,
                }
                for answer in self.answers
            ],
        }

    def to_markdown(self) -> str:
        answers = "".join(
            [
                f"### {answer.author} - {answer.timestamp}\n{answer.text}\n"
                for answer in self.answers
            ]
        )
        return f"""# {self.title}

## Question
{self.question.author} - {self.question.timestamp}
{self.question.text}

## Answers
{answers}
"""
