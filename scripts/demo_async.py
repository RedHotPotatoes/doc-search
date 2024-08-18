import asyncio
import logging
import time
from pathlib import Path

import hydra
import pretty_logging
import typer
from omegaconf import DictConfig, OmegaConf

from core.retrievers.document_retriever import DocumentRetriever
from core.summarizers.solution_analyzer import SolutionAnalyzer
from core.utils_hydra import register_resolvers

_log = logging.getLogger(Path(__file__).stem)


def load_config(conf_path: str) -> DictConfig:
    register_resolvers()
    return OmegaConf.load(conf_path)


def app(
    error_message: str = typer.Argument(..., help="The error message to search for in StackOverflow and GitHub Issues."),
    description: str = typer.Option("", help="The description of the error message."),
    config_path: Path = typer.Option("conf/prod.yaml", help="The path to the configuration file."),
):
    _log.info(f"Searching for error on the internet (Stackoverflow + GitHub issues)...")
    
    conf = load_config(config_path)
    document_retriever = hydra.utils.instantiate(conf.document_retriever)
    solution_analyzer = hydra.utils.instantiate(conf.solution_analyzer)

    elapsed = asyncio.run(generate_solution(document_retriever, solution_analyzer, error_message, description))
    _log.info(f"Retrieved documents in {elapsed['retrieve_elapsed']:0.2f} seconds.")
    _log.info(f"Analyzed documents in {elapsed['analyze_elapsed']:0.2f} seconds.")


async def generate_solution(document_retriever: DocumentRetriever, solution_analyzer: SolutionAnalyzer, error_message: str, description: str) -> str:
    s = time.time()
    documents = await document_retriever.retrieve_documents(error_message, description)
    retrieve_elapsed = time.time() - s
    if len(documents) == 0:
        _log.info("No documents found.")
        return
    
    s = time.time()
    async for chunk in solution_analyzer.generate_solution(
        error_message=error_message, 
        description=description, 
        documents=documents
    ):
        if isinstance(chunk, str):
            print(chunk, end="")
        else:
            print(chunk.content, end="")
    print()
    analyze_elapsed = time.time() - s
    return {
        "retrieve_elapsed": retrieve_elapsed,
        "analyze_elapsed": analyze_elapsed
    }
    

if __name__ == "__main__":
    """
        Usage: python -m scripts.demo_async <error_message>
        Examples: python -m scripts.demo_async "'glxplatform' object has no attribute 'osmesa'"
    """
    pretty_logging.setup("INFO")
    typer.run(app)
