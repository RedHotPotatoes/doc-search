import asyncio
from typing import Any, Sequence

from langchain.chains.llm import LLMChain
from langchain.chains.sequential import SequentialChain
from langchain.chat_models.base import BaseChatModel
from langchain.prompts import ChatPromptTemplate


class SummaryNode:
    _template = ""
    _input_variables = []

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm
        template = ChatPromptTemplate.from_template(self._template)
        summary_chain = LLMChain(llm=llm, prompt=template)
        self._chain = SequentialChain(
            chains=[summary_chain], input_variables=self._input_variables
        )

    def _preprocess_input(self, inputs: Any) -> str:
        raise NotImplementedError

    def summarize(self, inputs: Any):
        return self._chain.run(self._preprocess_input(inputs))

    def summarize_multiple(self, inputs: Sequence[Any]):
        return [self.summarize(input_) for input_ in inputs]

    async def async_summarize(self, inputs: Any):
        result = await self._chain.arun(self._preprocess_input(inputs))
        return result

    async def async_summarize_multiple(self, inputs: Sequence[Any]):
        result = await asyncio.gather(
            *[self.async_summarize(input_) for input_ in inputs]
        )
        return result
    

class Summarizer:
    async def summarize(self, inputs: Any) -> str:
        raise NotImplementedError
