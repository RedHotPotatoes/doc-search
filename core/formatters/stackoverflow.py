from core.stackoverflow import (CodeBlock, Comment, Data, Image, Lists,
                                        PlainText, StackOverflowAnswer,
                                        StackOverflowDocument,
                                        StackOverflowQuestion, Table)


def format_stackoverflow_document_to_markdown(document: StackOverflowDocument) -> str:
    question = format_stackoverflow_question(document.question)
    answers = format_stackoverflow_answers(document.answers)
    doc_tags = document.question.tags
    tags = ", ".join(doc_tags) if doc_tags else "*No tags provided.*"

    return f"""# {document.title}
## Question
{question}

## Tags
{tags}

## Answers
{answers}
"""


def format_stackoverflow_question(question: StackOverflowQuestion) -> str:
    question_text = "\n\n".join(format_data(data) for data in question.question)
    comments = format_comments(question.comments)
    return f"""{question_text}

## Comments to the question
{comments}
"""


def format_stackoverflow_answers(answers: list[StackOverflowAnswer]) -> str:
    if len(answers) == 0:
        return "*No answers provided.*"
    return "\n\n".join(format_stackoverflow_answer(answer, index + 1) for index, answer in enumerate(answers))


def format_stackoverflow_answer(
    answer: StackOverflowAnswer, index: int | None = None
) -> str:
    answer_text = "\n\n".join(format_data(data) for data in answer.answer)
    comments = format_comments(answer.comments)
    prefix = f"**Answer #{index}.** " if index is not None else ""
    return f"""{prefix}Answered by **{answer.username}**.
{answer_text}

Answer has **{answer.votes}** votes.

## Comments to the answer
{comments}
"""


def format_comments(comments: list[Comment]) -> str:
    if len(comments) == 0:
        return "*No comments provided.*"
    return "\n\n".join(format_comment(comment, index + 1) for index, comment in enumerate(comments))


def format_comment(comment: Comment, index: int | None) -> str:
    prefix = f"**Comment #{index}.** " if index is not None else ""
    return f"{prefix}Commented by **{comment.username}**. Comment text: {comment.text}"


def _plain_text_handler(data: PlainText) -> str:
    return data.text


def _code_block_handler(data: CodeBlock) -> str:
    return f"```{data.language}\n{data.text}\n```"


def _table_handler(data: Table) -> str:
    headers = " | ".join(data.headers)
    separator = " | ".join(["---"] * len(data.headers))
    rows = "\n".join(f"| {' | '.join(row)} |" for row in data.rows)
    return f"| {headers} | \n | {separator} | \n{rows}"


def _image_handler(data: Image) -> str:
    description = data.alt_text if data.alt_text else "No description provided."
    return f"<Image. {description}>"


def _lists_handler(data: Lists) -> str:
    items = "\n".join(f"* {item}" for item in data.items)
    return items


def format_data(data: Data) -> str:
    handler_map = {
        PlainText: _plain_text_handler,
        CodeBlock: _code_block_handler,
        Table: _table_handler,
        Image: _image_handler,
        Lists: _lists_handler,
    }
    handler = handler_map.get(type(data))
    if handler is None:
        raise ValueError(f"Unknown data type: {data}")
    return handler(data)
