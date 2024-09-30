import asyncio
from typing import Any, Coroutine, Sequence

from langchain.chat_models.base import BaseChatModel
from langchain.prompts import ChatPromptTemplate

from core.data_structures import MarkdownSerializable


class LLMNode:
    _template = ""

    def __init__(self, llm: BaseChatModel) -> None:
        prompt = ChatPromptTemplate.from_template(self._template)
        self._chain = prompt | llm

    def _preprocess_input(self, inputs: Any) -> str:
        raise NotImplementedError

    def invoke(self, inputs: Any):
        return self._chain.invoke(self._preprocess_input(inputs))

    def invoke_multiple(self, inputs: Sequence[Any]):
        return [self.invoke(input_) for input_ in inputs]
    
    async def ainvoke(self, inputs: Any) -> Coroutine[str, Any, Any]:
        result = await self._chain.ainvoke(self._preprocess_input(inputs))
        return result

    async def ainvoke_multiple(self, inputs: Sequence[Any]):
        result = await asyncio.gather(
            *[self.ainvoke(input_) for input_ in inputs]
        )
        return result
    
    async def astream(self, inputs: Any):
        async for result in self._chain.astream(self._preprocess_input(inputs)):
            yield result


class DocumentSummarizer(LLMNode):
    _template = (
        "You are expert in software development known for highly accurate and detailed summaries of the web-documents "
        "related to the software development such as StackOverflow, Github issues, Github discussions and others. \n\n"
        "You are given a document inside tag <document>. The document is in markdown format and consists of the "
        "question and answers. There could be nested structure of the document with replies/comments to the answers or even to question. "
        "There are also could be reactions, tags, vote counts, etc. \n\n"
        "Summarize the document. Think before you start summarizing: \n"
        "1. Summarize question. Keep the details but make it brief. Include code snippets, links, etc. Place question summary in <question> tag.\n"
        "2. Identify all the potential solutions from the answers. There could be three options: \n"
        " - Solutions provided <solutions_provided>, \n"
        " - No solutions <no_solutions>, \n"
        " - No solutions provided, but users provided some ideas that could be useful <useful_ideas>. \n"
        "3. Identify which case do we have and add appropriate tag <solutions_provided>, <no_solutions> or <useful_ideas>. \n"
        "4. If there are solutions <solutions_provided>, add brief overview of the solutions in <solutions_overview> tag. \n"
        "  4.1. Select the best solutions and summarize them. Place each solution summary in <solution> tag. "
        "Refer to the original document when summarizing the solutions to add necessary details including code snippets, links, etc. \n"
        "5. If there are no solutions <no_solutions>, just mention it. Do not make things up. \n"
        "6. If there are useful ideas <useful_ideas> write down the ideas in <idea> tag. \n\n"
        "<document>\n"
        "{document}\n"
        "</document>"
    )

    def _preprocess_input(self, document: MarkdownSerializable) -> str:
        return {"document": document.to_markdown()}
    

class Summarizer:
    async def summarize(self, inputs: Any) -> str:
        raise NotImplementedError
