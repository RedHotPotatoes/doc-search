from typing import Any

from markdownify import markdownify

from core.data_structures import (Comment, StackOverflowDocument,
                                  StackOverflowPost)


def parse_tags(raw_document: dict[str, Any]) -> list[str] | None:
    tags = raw_document["Tags"]
    if tags:
        return tags[1:-1].split("|")
    return


def parse_comment(raw_comment: dict[str, Any]) -> Comment:
    return Comment(
        text=raw_comment["Text"],
        creation_date=raw_comment["CreationDate"],
        score=raw_comment["Score"],
        user_id=raw_comment["UserId"]
    )


def parse_post(raw_post: dict[str, Any]) -> StackOverflowPost:
    text = markdownify(raw_post["Body"], heading_style="ATX")
    comments = [
        parse_comment(comment) for comment in raw_post["comments"]
    ]
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
    answers = [
        parse_post(answer) for answer in raw_document["answers"]
    ]
    return StackOverflowDocument(
        title=title,
        score=score,
        creation_date=creation_date,
        question=question,
        answers=answers
    )
