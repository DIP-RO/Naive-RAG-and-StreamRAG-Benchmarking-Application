from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.container import AppContainer
from app.models.schemas import BenchmarkRequest, ChatRequest, IngestDocumentRequest

router = APIRouter()


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    container = get_container(request)
    return {"status": "ok", "environment": container.settings.environment}


@router.post("/chat")
async def chat(request: Request, payload: ChatRequest) -> JSONResponse:
    container = get_container(request)
    response = await container.naive_pipeline.run(payload)
    return JSONResponse(response.model_dump())


@router.post("/chat/stream")
async def chat_stream(request: Request, payload: ChatRequest) -> StreamingResponse:
    container = get_container(request)

    async def event_stream():
        async for event in container.stream_pipeline.run(payload):
            yield f"data: {event}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/benchmark")
async def benchmark(request: Request, payload: BenchmarkRequest) -> JSONResponse:
    container = get_container(request)
    response = await container.benchmark_runner.run(payload)
    return JSONResponse(response.model_dump())


@router.post("/documents/ingest")
async def ingest_document(request: Request, payload: IngestDocumentRequest) -> JSONResponse:
    container = get_container(request)
    path = Path(payload.file_path)
    count = await container.document_ingestion.ingest_file(path)
    return JSONResponse({"chunks_ingested": count, "path": str(path)})
