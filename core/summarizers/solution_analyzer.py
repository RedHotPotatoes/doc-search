import asyncio
from typing import Any, AsyncGenerator, Dict, List, Tuple

from langchain.chat_models.base import BaseChatModel

from core.data_structures import GithubIssueDocument, StackOverflowDocument
from core.summarizers.github import (GitHubIssueDocumentSummarizerV2,
                                     GitHubIssueDocumentSummaryNodeV2)
from core.summarizers.stackoverflow import (StackOverflowDocumentSummarizerV2,
                                            StackOverflowDocumentSummaryNodeV2)
from core.summarizers.summarizer import Summarizer, SummaryNode

DocumentType = StackOverflowDocument | GithubIssueDocument


class DocumentsSolutionAggregator(SummaryNode):
    _template = (
        "Got the error message: {error_message}. {description}"
        "There is a list of documents that may contain solutions to the error message. {documents}."
        "First of all select the documents that are relevant to the error message. \n\n"
        "If there is no relevant document, reply 'No solutions found'. In case of relevant "
        "documents, reply a bullet list of solutions to the error message. "
        "The solutions should be detailed with explanation why it solves the error message. "
        "In the case there are code snippets or bash commands, include them in the solution. "
        "Reply only a bullet list of solutions."
    )

    def _preprocess_input(self, inputs: Dict[str, Any]) -> str:
        error_message = inputs.get("error_message")
        description = inputs.get("description", "")
        documents = inputs.get("documents")

        if len(documents) == 0:
            raise ValueError("No documents provided.")

        documents_text = "".join(
            f"\n\n## Document {index + 1}. \n\n{answer}"
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
            "stackoverflow": StackOverflowDocumentSummarizerV2(
                document_summary_node=StackOverflowDocumentSummaryNodeV2(llm),
            ),
            "github": GitHubIssueDocumentSummarizerV2(
                document_summary_node=GitHubIssueDocumentSummaryNodeV2(llm),
            ),
        }
        self._solution_aggregator = DocumentsSolutionAggregator(llm)

    async def generate_solution(
        self,
        error_message: str,
        documents: Dict[str, List[DocumentType]],
        description: str = "",
        yield_prompt: bool = False,
    ) -> str | AsyncGenerator[str, None]:
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
            "documents": [
                doc.content for doc in document_summaries
            ],
        }
        if yield_prompt:
            inputs_preproc = self._solution_aggregator._preprocess_input(
                solution_aggregator_inputs
            )
            yield self._solution_aggregator._chain.get_prompts()[0].format(**inputs_preproc)

        async for chunk in self._solution_aggregator.astream_summarize(
            solution_aggregator_inputs
        ):  
            if isinstance(chunk, str):
                yield chunk
            else:
                yield chunk.content


def unroll_dict(d: Dict[str, List[DocumentType]]) -> List[Tuple[str, DocumentType]]:
    return [(k, v) for k, vs in d.items() for v in vs]
