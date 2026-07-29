# Applied AI Engineer Assessment

Production-oriented full-stack AI agent comparing Naive RAG and StreamRAG in one system.

## What this repo demonstrates

- FastAPI backend with typed configuration, request-scoped logging, structured JSON logs, and async orchestration.
- Naive RAG and StreamRAG implemented as separate pipelines backed by shared retrieval, memory, and tool abstractions.
- Benchmarking focused on latency, TTFT, token usage, and a grounding-oriented summary.
- Next.js frontend that presents the comparison in an interview-friendly, production-style UI.
- Docker Compose for local end-to-end execution and GitHub Actions CI for backend and frontend validation.

## Architecture

```mermaid
flowchart LR
  U[User] --> F[Next.js Frontend]
  F --> A[FastAPI API]
  A --> O[Agent Orchestrator]
  O --> M[Conversation Memory]
  O --> R[Retrieval Layer]
  O --> T[Tool Registry]
  R --> Q[(Qdrant)]
  M --> S[(SQLite)]
  O --> L[LLM Provider]
  A --> B[Benchmark Runner]
  B --> O
```

### Folder Structure

```text
backend/
  src/app/
    api/
    agents/
    benchmark/
    config/
    core/
    memory/
    models/
    naiverag/
    retrieval/
    services/
    streamrag/
    tests/
    utils/
frontend/
  app/
  components/
  lib/
.github/workflows/
```

## Installation

### Backend

Create a virtual environment when developing locally:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Docker

```bash
docker compose up --build
```

Services:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/api
- Qdrant: http://localhost:6333
- Postgres: localhost:5432

## API

- `GET /api/health`
- `POST /api/chat`
- `POST /api/chat/stream`
- `POST /api/benchmark`
- `POST /api/documents/ingest`

## How StreamRAG Works

StreamRAG starts retrieval immediately, opens generation as soon as the initial context is ready, and continues broad retrieval in the background. New evidence can be emitted as context updates, which makes the system better suited for low-latency interactive experiences than a strictly synchronous retrieval-then-generate pipeline.

### Tradeoffs

- StreamRAG improves perceived responsiveness and can reduce time to first token.
- The implementation is more complex because it must manage concurrent retrieval, cancellation, and mid-stream context updates.
- Naive RAG is simpler and easier to reason about, so it remains a strong baseline for comparison and debugging.

## Benchmark

The benchmark endpoint runs both modes across repeated trials and records:

- latency
- time to first token
- retrieval time
- generation time
- prompt and completion tokens
- estimated cost
- grounding score and failure placeholders for evaluation hooks

## Testing

```bash
cd backend
pytest
```

## Future Improvements

- Replace heuristic tool routing with model-mediated function calling and policy constraints.
- Add real reranking and grounded evaluation against a labeled dataset.
- Persist benchmark runs into Postgres for trend analysis and reporting.
- Add websocket streaming in addition to SSE for richer client interactivity.
- Expand the document ingestion layer to support PDFs, HTML, and OCR pipelines.
