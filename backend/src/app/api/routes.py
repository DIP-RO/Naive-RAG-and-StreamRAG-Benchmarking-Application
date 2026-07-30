from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.container import AppContainer
from app.models.schemas import BenchmarkRequest, ChatRequest, IngestDocumentRequest

router = APIRouter()

ALLOWED_DOC_DIRS = [Path("documents").resolve(), Path("../documents").resolve()]


def _resolve_safe_path(file_path: str) -> Path:
    resolved = Path(file_path).resolve()
    for allowed in ALLOWED_DOC_DIRS:
        if allowed.exists() and str(resolved).startswith(str(allowed)):
            return resolved
    raise HTTPException(status_code=403, detail="Access denied: path outside allowed directories")


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    container: AppContainer | None = getattr(request.app.state, "container", None)
    if container is None:
        return {"status": "degraded", "environment": "unknown"}
    return {"status": "ok", "environment": container.settings.environment}


@router.post("/chat")
async def chat(request: Request, payload: ChatRequest) -> JSONResponse:
    container = request.app.state.container
    response = await container.naive_pipeline.run(payload)
    return JSONResponse(response.model_dump())


@router.post("/chat/stream")
async def chat_stream(request: Request, payload: ChatRequest) -> StreamingResponse:
    container = request.app.state.container

    async def event_stream():
        async for event in container.stream_pipeline.run(payload):
            yield f"data: {event}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/benchmark")
async def benchmark(request: Request, payload: BenchmarkRequest) -> JSONResponse:
    container = request.app.state.container
    response = await container.benchmark_runner.run(payload)
    return JSONResponse(response.model_dump())


@router.post("/documents/ingest")
async def ingest_document(request: Request, payload: IngestDocumentRequest) -> JSONResponse:
    container = request.app.state.container
    path = _resolve_safe_path(payload.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    if not path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    count = await container.document_ingestion.ingest_file(path)
    return JSONResponse({"chunks_ingested": count, "path": str(path)})
