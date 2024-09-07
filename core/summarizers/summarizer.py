import asyncio
from typing import Any, Coroutine, Sequence

from langchain.chat_models.base import BaseChatModel
from langchain.prompts import ChatPromptTemplate


class SummaryNode:
    _template = ""

    def __init__(self, llm: BaseChatModel) -> None:
        prompt = ChatPromptTemplate.from_template(self._template)
        self._chain = prompt | llm

    def _preprocess_input(self, inputs: Any) -> str:
        raise NotImplementedError

    def summarize(self, inputs: Any):
        return self._chain.invoke(self._preprocess_input(inputs))

    def summarize_multiple(self, inputs: Sequence[Any]):
        return [self.summarize(input_) for input_ in inputs]
    
    async def async_summarize(self, inputs: Any) -> Coroutine[str, Any, Any]:
        result = await self._chain.ainvoke(self._preprocess_input(inputs))
        return result

    async def async_summarize_multiple(self, inputs: Sequence[Any]):
        result = await asyncio.gather(
            *[self.async_summarize(input_) for input_ in inputs]
        )
        return result
    
    async def astream_summarize(self, inputs: Any):
        async for result in self._chain.astream(self._preprocess_input(inputs)):
            yield result
    

class Summarizer:
    async def summarize(self, inputs: Any) -> str:
        raise NotImplementedError
