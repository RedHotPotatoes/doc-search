from typing import Any, Dict, List

from core.data_structures import GithubIssueDocument, GithubIssueComment
from core.summarizes.summarizer import Summarizer, SummaryNode


class GithubIssueQuestionSummaryNode(SummaryNode):
    _template = (
        "Summarize the question in one or a couple of sentences. "
        "Make sure to include the main problem and the context. "
        "The question is from the GitHub issues page. The question may contain code snippets, "
        "tables, and enumerations; all the text is in markdown format. " 
        "## Question: {question_text}. {reactions_text}"
    )
    _input_variables = ["question_text", "reactions_text"]

    def _preprocess_input(self, inputs: GithubIssueComment) -> str:
        question_text = inputs.text
        reactions = inputs.reactions
        if reactions:
            reactions_text = ", ".join(f"{reaction}: {count}" for reaction, count in reactions.items())
            reactions_text = f"The question has reactions: {reactions_text}"
        else:
            reactions_text = ""
        return {
            "question_text": question_text,
            "reactions_text": reactions_text,
        }


class GithubIssueReplySummaryNode(SummaryNode):
    _template = (
        "{question_prefix}Give a concise summary of the reply to the question. "
        "Summarize the reply clearly and concisely. Keep code snippets and shell commands. "
        "The reply may contain code snippets, tables, and enumerations; all the text is in "
        "markdown format. ## Reply: {reply_text}.{reactions_text}"
    )
    _input_variables = ["question_prefix", "reply_text", "reactions_text"]

    def _preprocess_input(self, inputs: GithubIssueComment | Dict[str, Any]) -> str:
        if isinstance(inputs, GithubIssueComment):
            question = None
            reply = inputs
        else:
            reply = inputs.get("reply")
            question = inputs.get("question", None)
        reply_text = reply.text
        reactions = reply.reactions
        if reactions:
            reactions_text = ", ".join(f"{reaction}: {count}" for reaction, count in reactions.items())
            reactions_text = f"The reply has reactions: {reactions_text}"
        else:
            reactions_text = ""
        
        prefix = ""
        if question is not None:
            prefix = f"There is an reply to ## Question: {question}. "
        return {
            "question_prefix": prefix,
            "reply_text": reply_text,
            "reactions_text": reactions_text,
        }


class GitHubIssueDocumentSummaryNode(SummaryNode):
    _template = (
        "Summarize the GitHub issue post. It's not exact post, the question and replies "
        "are summarized. Identify the problem and formulate solutions. "
        "The summary should contain problem and a bullet list of solutions if the solutions exist. "
        "## Question: {question}. ## Replies: {replies}"
    )
    _input_variables = ["question", "replies"]

    def _concatenate_replies(
        self, replies: List[str]
    ) -> str:
        return "\n\n".join(
            f"**Reply {index + 1}.** {reply}" for index, reply in enumerate(replies)
        )

    def _preprocess_input(self, inputs: Dict[str, Any]) -> str:
        question = inputs.get("question")
        replies = inputs.get("replies")
        if len(inputs) == 0:
            return {
                "question": question,
                "replies": "*No replies provided.*",
            }
        replies = self._concatenate_replies(replies)
        return {"question": question, "replies": replies}


class GitHubIssueDocumentSummarizer(Summarizer):
    def __init__(
        self,
        question_summary_node: GithubIssueQuestionSummaryNode,
        reply_summary_node: GithubIssueReplySummaryNode,
        document_summary_node: GitHubIssueDocumentSummaryNode,
    ) -> None:
        self._question_summary_node = question_summary_node
        self._reply_summary_node = reply_summary_node
        self._document_summary_node = document_summary_node
    
    async def summarize(
        self, document: GithubIssueDocument,
    ) -> str:
        question_summary = await self._question_summary_node.async_summarize(document.question)
        reply_summarizer_inputs = [
            {"question": question_summary, "reply": reply}
            for reply in document.answers
        ]
        replies_summary = await self._reply_summary_node.async_summarize_multiple(
            reply_summarizer_inputs
        )
        document_summarizer_inputs = {
            "question": question_summary,
            "replies": replies_summary,
        }
        return await self._document_summary_node.async_summarize(document_summarizer_inputs)
