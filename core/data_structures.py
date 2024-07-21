import datetime
from dataclasses import dataclass
from datetime import datetime
from typing import List


class MarkdownSerializable:
    def to_markdown(self) -> str:
        raise NotImplementedError


class JsonSerializable:
    def to_json(self) -> str:
        raise NotImplementedError


@dataclass
class Comment:
    text: str
    creation_date: datetime
    score: int
    user_id: int | None = None


@dataclass
class StackOverflowPost:
    text: str
    comments: List[Comment]
    tags: List[str] | None
    creation_date: datetime
    last_edit_date: datetime


@dataclass
class StackOverflowDocument(MarkdownSerializable, JsonSerializable):
    title: str
    score: int 
    creation_date: str
    question: StackOverflowPost
    answers: list[StackOverflowPost]
    accepted_index: int | None = None

    def to_json(self) -> str:
        return {
            "title": self.title,
            "score": self.score,
            "creation_date": self.creation_date,
            "question": {
                "text": self.question.text,
                "comments": [
                    {
                        "text": comment.text,
                        "creation_date": comment.creation_date,
                        "score": comment.score,
                    }
                    for comment in self.question.comments
                ],
                "tags": self.question.tags,
                "creation_date": self.question.creation_date,
                "last_edit_date": self.question.last_edit_date,
            },
            "answers": [
                {
                    "text": answer.text,
                    "comments": [
                        {
                            "text": comment.text,
                            "creation_date": comment.creation_date,
                            "score": comment.score,
                        }
                        for comment in answer.comments
                    ],
                    "tags": answer.tags,
                    "creation_date": answer.creation_date,
                    "last_edit_date": answer.last_edit_date,
                }
                for answer in self.answers
            ],
            "accepted_index": self.accepted_index,
        }
    
    def to_markdown(self) -> str:
        answers = "".join(
            [
                f"### {answer.creation_date}\n{answer.text}\n"
                for answer in self.answers
            ]
        )
        return f"""# {self.title}

## Question
{self.question.creation_date}
{self.question.text}

## Answers
{answers}
"""


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
    answers: list[GithubIssueComment]

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
