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
