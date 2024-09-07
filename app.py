import datetime
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Any

import bson
import hydra
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from omegaconf import OmegaConf

from core.conversation import (get_chat_history, get_conversation_runnable,
                               serialize_conversation)
from core.db import AsyncMongoDB
from core.retrievers.document_retriever import DocumentRetriever
from core.status_codes import HttpStatusCode
from core.summarizers.solution_analyzer import SolutionAnalyzer
from core.utils_hydra import register_resolvers
from core.utils_stream import parse_stream_chunk


@dataclass
class GenerateConfig:
    error_message: str
    description: str
    documents: dict[str, list[dict[str, Any]]]
    yield_prompt: bool
    links: list[str]


@dataclass 
class FollowUpConfig:
    user_text: str
    query_id: str


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

register_resolvers()
conf = OmegaConf.load("conf/prod.yaml")

document_retriever: DocumentRetriever = hydra.utils.instantiate(conf.document_retriever)
solution_analyzer: SolutionAnalyzer = hydra.utils.instantiate(conf.solution_analyzer)
conversation_llm = hydra.utils.instantiate(conf.conversation_llm)

mongo_host = os.getenv("MONGODB_HOST", "mongodb")
mongo_port = os.getenv("MONGODB_PORT", 27017)
host = f"mongodb://{mongo_host}:{mongo_port}/"

db = AsyncMongoDB(
    host,
    default_db="troubleshooting",
    default_collection="search_queries",
    username=os.getenv("MONGODB_ADMIN_USER"),
    password=os.getenv("MONGODB_ADMIN_PASS"),
)


async def generate_request_handler(config: GenerateConfig):
    prompt = None
    llm_response = []
    async for chunk in solution_analyzer.generate_solution(
        config.error_message, config.documents, config.description, config.yield_prompt
    ):
        if config.yield_prompt and prompt is None:
            prompt = chunk
        else:
            llm_response.append(chunk)
            yield chunk

    llm_response = "".join(llm_response)
    prompt = prompt or config.error_message

    conversation = serialize_conversation([prompt, llm_response])
    curr_time = datetime.now(UTC)
    data = {
        "user_id": None,
        "query_text": config.error_message,
        "links": config.links,
        "created_at": curr_time,
        "updated_at": curr_time,
        "conversation": conversation,
        "search_engine": "custom",
    }
    db_response = await db.insert(data)
    query_id = str(db_response.inserted_id)

    links_str = ", ".join(
        [f"[{index + 1}]({link})" for index, link in enumerate(config.links)]
    )
    yield ("\n\n" f" - **References:** ({links_str})")
    yield ("\n\n" f" - **QUERY ID:** {query_id}")


async def follow_up_request_handler(config: FollowUpConfig):
    conversation_runnable = get_conversation_runnable(
        conversation_llm, partial(get_chat_history, mongo_client=db)
    )
    async for chunk in conversation_runnable.astream(
        {"question": config.user_text}, config={"configurable": {"session_id": config.query_id}}
    ):
        yield parse_stream_chunk(chunk)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.post("/generate_solution")
async def generate_solution(error_message: str, description: str = ""):
    documents, links = await document_retriever.retrieve_documents(
        error_message, description
    )
    if len(documents) == 0:
        return JSONResponse(
            status_code=HttpStatusCode.NO_CONTENT.value,
            content={"error": "Unable to find relevant documents."},
        )
    config = GenerateConfig(
        error_message=error_message,
        description=description,
        documents=documents,
        yield_prompt=True,
        links=links,
    )
    return StreamingResponse(
        generate_request_handler(config),
        media_type="text/plain",
    )


@app.post("/follow_up")
async def follow_up(user_text: str, query_id: str):
    if not bson.ObjectId.is_valid(query_id):
        return JSONResponse(
            status_code=HttpStatusCode.BAD_REQUEST.value,
            content={"error": "Query ID is not valid."},
        )
    if await db.get_by_id(query_id) is None:
        return JSONResponse(
            status_code=HttpStatusCode.NOT_FOUND.value,
            content={"error": "Query ID not found."},
        )
    config = FollowUpConfig(user_text=user_text, query_id=query_id)
    return StreamingResponse(
        follow_up_request_handler(config),
        media_type="text/plain",
    )
