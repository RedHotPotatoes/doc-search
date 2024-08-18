import hydra
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from omegaconf import OmegaConf

from core.retrievers.document_retriever import DocumentRetriever
from core.summarizers.solution_analyzer import SolutionAnalyzer
from core.utils_hydra import register_resolvers

app = FastAPI()

register_resolvers()
conf = OmegaConf.load("conf/prod.yaml")

document_retriever: DocumentRetriever = hydra.utils.instantiate(conf.document_retriever)
solution_analyzer: SolutionAnalyzer = hydra.utils.instantiate(conf.solution_analyzer)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.post("/generate_solution")
async def generate_solution(error_message: str, description: str = ""):
    documents = await document_retriever.retrieve_documents(error_message, description)
    if len(documents) == 0:
        return JSONResponse(content={"error": "Unable to find relevant documents."})
    return StreamingResponse(
        solution_analyzer.generate_solution(
            error_message=error_message, description=description, documents=documents
        ),
        media_type="text/plain",
    )
