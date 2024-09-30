from typing import Any, Dict, List

from core.parsers.stackoverflow_index import (StackOverflowDocument)
from core.parsers.stackoverflow_index import StackOverflowComment, StackOverflowPost
from core.summarizers.summarizer import Summarizer, LLMNode
from core.utils import deprecated


@deprecated
def format_comments(comments: list[StackOverflowComment]) -> str:
    if len(comments) == 0:
        return "*No comments provided.*"
    return "\n\n".join(
        format_comment(comment, index + 1) for index, comment in enumerate(comments)
    )


@deprecated
def format_comment(comment: StackOverflowComment, index: int | None) -> str:
    prefix = f"**Comment {index}.** " if index is not None else ""
    return f"{prefix}Comment text: {comment.text}"


@deprecated
class StackOverflowDocumentSummaryNodeV2(LLMNode):
    _template = (
        "Summarize the Stackoverflow post. Identify the problem from the question and formulate solutions. "
        "The summary should contain problem and a bullet list of solutions if the solutions exist. Take into account "
        "comments to the question and answers since some of them may contain valuable information. "
        "## Question: {question}. "
        "## Answers: {answers}"
    )

    def _format_post(self, post: StackOverflowPost) -> str:
        if len(post.comments) > 0:
            comments = format_comments(post.comments)
            return f"{post.text}\n\nComments: {comments}"
        return post.text

    def _concatenate_answers(self, answers: List[StackOverflowPost]) -> str:
        return "\n\n".join(
            f"**Answer {index + 1}.** {self._format_post(answer)}"
            for index, answer in enumerate(answers)
        )

    def _preprocess_input(self, inputs: StackOverflowDocument) -> str:
        question = self._format_post(inputs.question)
        answers = inputs.answers
        if len(answers) == 0:
            return {
                "question": question,
                "answers": "*No answers provided.*",
            }
        answers = self._concatenate_answers(answers)
        return {"question": question, "answers": answers}


@deprecated
class StackOverflowDocumentSummarizerV2(Summarizer):
    def __init__(
        self,
        document_summary_node: LLMNode,
    ) -> None:
        self._document_summary_node = document_summary_node

    async def summarize(
        self,
        document: StackOverflowDocument,
    ) -> str:
        return await self._document_summary_node.ainvoke(document)


@deprecated
class StackOverflowQuestionSummaryNode(LLMNode):
    _template = (
        "Summarize the question in one or a couple of sentences. "
        "Make sure to include the main problem and the context. "
        "The question is from the Stackoverlow post. The question may contain code snippets, "
        "tables, and enumerations; all the text is in markdown format. "
        "## Question: {question_text}. {comments_text}{tags_text}"
    )

    def _preprocess_input(self, inputs: StackOverflowPost) -> str:
        comments = inputs.comments
        if comments:
            comments_text = f"The question has comments: {format_comments(comments)}. "
        else:
            comments_text = ""

        tags = inputs.tags
        if tags:
            tags_text = f"User specified tags: {', '.join(tags)}."
        else:
            tags_text = ""

        question_text = inputs.text
        return {
            "question_text": question_text,
            "comments_text": comments_text,
            "tags_text": tags_text,
        }


@deprecated
class StackOverflowAnswerSummaryNode(LLMNode):
    _template = (
        "{question_prefix}Give a concise summary of the answer to the question. "
        "Summarize the answer clearly and concisely. If there is no answer to the question, "
        "specify that there is no answer."
        "The answer may contain code snippets, tables, and enumerations; all the text is in "
        "markdown format. ## Answer: {answer_text}. {comments_text}"
    )

    def _preprocess_input(self, inputs: StackOverflowPost | Dict[str, Any]) -> str:
        if isinstance(inputs, StackOverflowPost):
            question = None
            answer = inputs
        else:
            answer = inputs.get("answer")
            question = inputs.get("question", None)
        answer_text = answer.text
        comments = answer.comments
        if comments:
            comments_text = (
                f"The answer has comments: {format_comments(comments)}. "
                "The comments may argue the drawbacks of the answer or "
                "provide additional information."
            )
        else:
            comments_text = ""

        prefix = ""
        if question is not None:
            prefix = f"There is an answer to ## Question:  {question}. "
        return {
            "question_prefix": prefix,
            "answer_text": answer_text,
            "comments_text": comments_text,
        }


@deprecated
class StackOverflowDocumentSummaryNode(LLMNode):
    _template = (
        "Summarize the Stackoverflow post. It's not exact post, the question and answers "
        "are summarized. Identify the problem and formulate solutions. "
        "The summary should contain problem and a bullet list of solutions if the solutions exist. "
        "## Question: {question}. ## Answers: {answers}"
    )

    def _concatenate_answers(self, answers: List[str]) -> str:
        return "\n\n".join(
            f"**Answer {index + 1}.** {answer}" for index, answer in enumerate(answers)
        )

    def _preprocess_input(self, inputs: Dict[str, Any]) -> str:
        question = inputs.get("question")
        answers = inputs.get("answers")
        if len(inputs) == 0:
            return {
                "question": question,
                "answers": "*No answers provided.*",
            }
        answers = self._concatenate_answers(answers)
        return {"question": question, "answers": answers}


@deprecated
class StackOverflowDocumentSummarizer(Summarizer):
    def __init__(
        self,
        question_summary_node: LLMNode,
        answer_summary_node: LLMNode,
        document_summary_node: LLMNode,
    ) -> None:
        self._question_summary_node = question_summary_node
        self._answer_summary_node = answer_summary_node
        self._document_summary_node = document_summary_node

    async def summarize(
        self,
        document: StackOverflowDocument,
    ) -> str:
        question_summary = await self._question_summary_node.ainvoke(
            document.question
        )
        answer_summarizer_inputs = [
            {"question": question_summary, "answer": answer}
            for answer in document.answers
        ]
        answers_summary = await self._answer_summary_node.ainvoke_multiple(
            answer_summarizer_inputs
        )
        document_summarizer_inputs = {
            "question": question_summary,
            "answers": answers_summary,
        }
        return await self._document_summary_node.ainvoke(
            document_summarizer_inputs
        )
