from dataclasses import dataclass
from datetime import datetime
from typing import Any, List

from markdownify import markdownify

from core.data_structures import JsonSerializable, MarkdownSerializable


@dataclass
class StackOverflowComment:
    text: str
    creation_date: datetime
    score: int
    user_id: int | None = None


@dataclass
class StackOverflowPost:
    text: str
    comments: List[StackOverflowComment]
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
            [f"### {answer.creation_date}\n{answer.text}\n" for answer in self.answers]
        )
        return f"""# {self.title}

## Question
{self.question.creation_date}
{self.question.text}

## Answers
{answers}
"""


def parse_tags(raw_document: dict[str, Any]) -> list[str] | None:
    tags = raw_document["Tags"]
    if tags:
        return tags[1:-1].split("|")
    return


def parse_comment(raw_comment: dict[str, Any]) -> StackOverflowComment:
    return StackOverflowComment(
        text=raw_comment["Text"],
        creation_date=raw_comment["CreationDate"],
        score=raw_comment["Score"],
        user_id=raw_comment["UserId"],
    )


def parse_post(raw_post: dict[str, Any]) -> StackOverflowPost:
    text = markdownify(raw_post["Body"], heading_style="ATX")
    comments = [parse_comment(comment) for comment in raw_post["comments"]]
    tags = parse_tags(raw_post)
    return StackOverflowPost(
        text=text,
        comments=comments,
        tags=tags,
        creation_date=raw_post["CreationDate"],
        last_edit_date=raw_post["LastEditDate"],
    )


def parse_stackoverflow_question_page(raw_document: dict[str, Any]):
    title = raw_document["Title"]
    score = raw_document["Score"]
    creation_date = raw_document["CreationDate"]
    question = parse_post(raw_document)
    answers = [parse_post(answer) for answer in raw_document["answers"]]
    return StackOverflowDocument(
        title=title,
        score=score,
        creation_date=creation_date,
        question=question,
        answers=answers,
    )
