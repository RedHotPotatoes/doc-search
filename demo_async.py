import asyncio
import logging
import time
from pathlib import Path
from typing import List

import aiohttp
import pretty_logging
import typer
from langchain_openai import ChatOpenAI

from core.cache.cache import DocumentsCache
from core.cache.persistent_cache import DocumentsPersistentCache
from core.parsers.stackoverflow import parse_stackoverflow_question_page
from core.summarize.stackoverflow import (
    DocumentsSolutionAggregator, StackOverflowAnswerSummarizer,
    StackoverflowDocumentSolutionSummarizer, StackOverflowQuestionSummarizer,
    Summarizer, summarize_stackoverflow_documents)
from core.utils import search_stackoverflow

_log = logging.getLogger(Path(__file__).stem)

cache_lock = asyncio.Lock()


async def fetch_url(session, url):
    async with session.get(url) as response:
        return await response.text()


async def load_pages_from_urls(links: List[str]):
    async with aiohttp.ClientSession() as session:
        documents = await asyncio.gather(*[fetch_url(session, link) for link in links])
    return documents


async def load_pages(
    links: List[str],
    cache: DocumentsCache | None = None,
):
    cached_links, non_cached_links = [], []
    cached_documents, non_cached_documents = [], []
    async with cache_lock:
        if cache is not None:
            for link in links:
                if link in cache:
                    cached_links.append(link)
                else:
                    non_cached_links.append(link)
        else:
            non_cached_links = links
        cached_documents = [cache.query_document(link) for link in cached_links]

    _log.info(f"Loaded {len(cached_documents)} documents from cache.")
    if len(non_cached_links) > 0:
        non_cached_documents = await load_pages_from_urls(non_cached_links)
    return cached_documents, non_cached_documents, cached_links, non_cached_links


async def resolve_error(
    question_summarizer: Summarizer,
    answer_summarizer: Summarizer,
    solution_summarizer: Summarizer,
    solution_aggregator: Summarizer,
    error_message: str | None = None,
    links: List[str] | None = None,
    cache: DocumentsCache | None = None,
    top_k_pages: int = 10,
    update_cache: bool = True,
):
    if error_message is None and links is None:
        raise ValueError("Either error_message or links must be provided.")
    if links is None:
        links = search_stackoverflow(error_message)
    if not links:
        _log.info("Unable to find relevant data from the internet.")
        return "Unable to find relevant data from the internet."

    links = links[:top_k_pages]
    cached_documents, non_cached_documents, cached_links, non_cached_links = (
        await load_pages(links, cache)
    )
    if cache is not None and update_cache:
        async with cache_lock:
            for link, document in zip(non_cached_links, non_cached_documents):
                cache.insert_document(link, document)

    documents = [parse_stackoverflow_question_page(doc) for doc in cached_documents] + [
        parse_stackoverflow_question_page(doc) for doc in non_cached_documents
    ]
    _log.info(f"Parsed {len(documents)} documents.")

    solution = await summarize_stackoverflow_documents(
        error_message,
        documents,
        answer_summarizer=answer_summarizer,
        solution_summarizer=solution_summarizer,
        solution_aggregator=solution_aggregator,
        question_summarizer=question_summarizer
    )
    _log.info(f"Solution: {solution}")
    return solution


def app(
    error_message: str = typer.Argument(..., help="The error message to search for in StackOverflow."),
    model_name: str = typer.Option("gpt-3.5-turbo", help="The model name to use."),
):
    _log.info(f"Searching for '{error_message}' in StackOverflow...")

    cache = DocumentsPersistentCache.from_config(".cache")

    llm = ChatOpenAI(model_name=model_name)
    question_summarizer = StackOverflowQuestionSummarizer(llm)
    answer_summarizer = StackOverflowAnswerSummarizer(llm)
    solution_summarizer = StackoverflowDocumentSolutionSummarizer(llm)
    solution_aggregator = DocumentsSolutionAggregator(llm)

    links = search_stackoverflow(error_message)
    s = time.perf_counter()
    asyncio.run(
        resolve_error(
            links=links,
            question_summarizer=question_summarizer,
            answer_summarizer=answer_summarizer,
            solution_summarizer=solution_summarizer,
            solution_aggregator=solution_aggregator,
            cache=cache,
            top_k_pages=3
        )
    )
    elapsed = time.perf_counter() - s
    _log.info(f"executed in {elapsed:0.2f} seconds.")


if __name__ == "__main__":
    """
        Usage: python demo_async.py <error_message>
        Examples: python demo_async.py "IndentationError: expected an indented block"
                  python demo_async.py "IndentationError: expected an indented block" --model-name "gpt-4-0125-preview"  
    """
    pretty_logging.setup("INFO")
    typer.run(app)
