from typing import Any, AsyncGenerator

from core.data_structures import MarkdownSerializable
from core.summarizers.summarizer import LLMNode
from core.utils_stream import parse_stream_chunk


class SolutionAnalyzer(LLMNode):
    _template = (
        "You are expert in software development known for abilities to highly accurate analyze the error messages. \n\n"
        "You are given the error message inside tag <error_message>. You need to analyze the error message and reply "
        "the list of potential solutions to the error message. \n\n"
        "{document_context_prompt}"
        "Follow the output format: \n"
        "1. Brief introduction \n"
        "2. ## Solutions \n"
        "3. Solution title. The title begins with ### and is bold. \n"
        "4. Brief explanation why this solution solves the error message. \n"
        "5. Finally, provide the detailed step by step instructions how to solve the error message. Start with #### Instructions. "
        "Include the code snippets, bash commands, links to the code snippets, etc. Don't be lazy, be detailed. "
        "Use enumerated lists for step by step instructions. \n"
        "Strictly follow code snippet format: \n"
        "```<language>\n"
        "<code snippet>\n"
        "```\n"
        "For instance, \n"
        "```python\n"
        "print('Hello, world!')\n"
        "```\n\n"
        "Don't forget newlines when you use code snippets!!! \n\n"
        "<error_message>\n"
        "{error_message}\n"
        "</error_message>"
    )

    _document_context_prompt = (
        "Before you start to analyze the error message, look at the list of documents that *may* contain solutions to the error message. "
        "Each document is inside <document> tag. First of all, documents are the summaries of the web-documents such as StackOverflow, Github issues, "
        "Github discussions and others. The summaries contain the question in <question> tag and potential solutions in <solution> tags. "
        "Some documents may not contain solutions. \n\n"
        "Start with your own solutions, use the documents to reinforce your knowledge in the field. \n\n"
        "{documents}\n\n"
    )

    def _preprocess_input(self, inputs: dict[str, Any]) -> str:
        error_message = inputs.get("error_message")
        documents = inputs.get("documents")

        if len(documents) == 0:
            context_prompt = ""
        else:
            documents_text = "\n\n".join(
                f"<document>\n{doc}\n</document>"
                for doc in documents
            )
            context_prompt = self._document_context_prompt.format(
                documents=documents_text
            )

        return {
            "error_message": error_message,
            "document_context_prompt": context_prompt,
        }


class SolutionAggregator:
    def __init__(self, summarizer: LLMNode, solution_analyzer: LLMNode) -> None:
        self._summarizer = summarizer
        self._solution_analyzer = solution_analyzer

    async def generate_solution(
        self,
        error_message: str,
        documents: list[MarkdownSerializable],
        description: str = "",
        yield_prompt: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        document_summaries = await self._summarizer.ainvoke_multiple(documents)
        solution_aggregator_inputs = {
            "error_message": error_message,
            "description": description,
            "documents": [
                doc.content for doc in document_summaries
            ],
        }
        if yield_prompt:
            inputs_preproc = self._solution_analyzer._preprocess_input(
                solution_aggregator_inputs
            )
            yield self._solution_analyzer._chain.get_prompts()[0].format(**inputs_preproc)

        async for chunk in self._solution_analyzer.astream(
            solution_aggregator_inputs
        ):  
            yield parse_stream_chunk(chunk)
