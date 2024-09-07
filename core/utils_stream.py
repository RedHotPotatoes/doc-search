from langchain_core.messages import BaseMessage


def parse_stream_chunk(chunk: str | BaseMessage) -> str:
    if isinstance(chunk, BaseMessage):
        return chunk.content
    return chunk
