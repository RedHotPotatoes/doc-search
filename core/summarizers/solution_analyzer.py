import asyncio
from typing import Any, Dict, List, Tuple

from langchain.chat_models.base import BaseChatModel

from core.data_structures import GithubIssueDocument, StackOverflowDocument
from core.summarizers.github import (GitHubIssueDocumentSummarizer,
                                     GitHubIssueDocumentSummaryNode,
                                     GithubIssueQuestionSummaryNode,
                                     GithubIssueReplySummaryNode)
from core.summarizers.stackoverflow import (StackOverflowAnswerSummaryNode,
                                            StackOverflowDocumentSummarizer,
                                            StackOverflowDocumentSummaryNode,
                                            StackOverflowQuestionSummaryNode)
from core.summarizers.summarizer import Summarizer, SummaryNode

DocumentType = StackOverflowDocument | GithubIssueDocument


class DocumentsSolutionAggregator(SummaryNode):
    _template = (
        "Got the error message: {error_message}. {description}"
        "There is a list of documents that may contain solutions to the error message. {documents}."
        "First of all select the documents that are relevant to the error message. "
        "If there is no relevant document, reply 'No solutions found'. In case of relevant "
        "documents, reply a bullet list of detailed solutions to the error message. "
        "Reply only a bullet list of solutions."
    )
    _input_variables = ["error_message", "description", "documents"]

    def _preprocess_input(self, inputs: Dict[str, Any]) -> str:
        error_message = inputs.get("error_message")
        description = inputs.get("description", "")
        documents = inputs.get("documents")

        if len(documents) == 0:
            raise ValueError("No documents provided.")

        documents_text = "\n\n".join(
            f"**Document {index + 1}.** {answer}"
            for index, answer in enumerate(documents)
        )
        return {
            "error_message": error_message,
            "description": description,
            "documents": documents_text,
        }


class SolutionAnalyzer:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

        self._summarizers: dict[str, Summarizer] = {
            "stackoverflow": StackOverflowDocumentSummarizer(
                question_summary_node=StackOverflowQuestionSummaryNode(llm),
                answer_summary_node=StackOverflowAnswerSummaryNode(llm),
                document_summary_node=StackOverflowDocumentSummaryNode(llm),
            ),
            "github": GitHubIssueDocumentSummarizer(
                question_summary_node=GithubIssueQuestionSummaryNode(llm),
                reply_summary_node=GithubIssueReplySummaryNode(llm),
                document_summary_node=GitHubIssueDocumentSummaryNode(llm),
            ),
        }
        self._solution_aggregator = DocumentsSolutionAggregator(llm)

    async def generate_solution(
        self,
        error_message: str,
        documents: Dict[str, List[DocumentType]],
        description: str = "",
    ) -> str:
        document_summaries = []
        documents_unroll = unroll_dict(documents)
        document_summaries = await asyncio.gather(
            *[
                self._summarizers[document_type].summarize(document)
                for document_type, document in documents_unroll
            ]
        )
        solution_aggregator_inputs = {
            "error_message": error_message,
            "description": description,
            "documents": document_summaries,
        }
        return await self._solution_aggregator.async_summarize(
            solution_aggregator_inputs
        )


def unroll_dict(d: Dict[str, List[DocumentType]]) -> List[Tuple[str, DocumentType]]:
    return [(k, v) for k, vs in d.items() for v in vs]
