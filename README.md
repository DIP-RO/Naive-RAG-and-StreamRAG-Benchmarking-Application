# Naive RAG vs StreamRAG — Benchmarking Application

AI Agent comparing Naive RAG and StreamRAG in a full-stack production system with guardrails, hallucination reduction, and observability.

## Deliverables Checklist

- [x] **Public GitHub repo** with code, README, and benchmark report
- [x] **One-command setup**: `docker compose up --build`
- [x] **README** with architecture, setup, and design decisions
- [x] **Benchmark scripts**: `python benchmark/run.py`
- [x] **Test dataset**: `benchmark/test_set.json` (22 queries with expected answers)
- [x] **Example documents**: `documents/` (10 files for RAG ingestion)
- [x] **Benchmark report**: `BENCHMARK.md`
- [ ] **Video**: 5-min walkthrough (intro, architecture, demo, tradeoffs)

## Architecture

### System Flow

```mermaid
flowchart LR
    subgraph Frontend["Frontend (Next.js 14)"]
        Landing["/ (Landing)"]
        Dash["/benchmark (Dashboard)"]
        Client["lib/api.ts"]
    end
    subgraph API["FastAPI Backend"]
        Routes["routes.py"]
        Container["container.py (DI)"]
        Graph["orchestrator.py (StateGraph)"]
        Guard["guardrails.py"]
        LLM["llm.py (ChatOpenAI)"]
        RAG(["RAG Pipelines"])
        Tools(["Tool Registry"])
        Skills(["SkillRegistry"])
        Mem(["Memory (SQLite)"])
        Vec(["Vector Store (Qdrant)"])
    end
    subgraph External["External"]
        Q["Qdrant"]
        OAI["OpenAI / OpenRouter"]
        FS["documents/"]
    end

    Landing --> Routes
    Dash --> Routes
    Routes --> Container
    Container --> Graph
    Graph --> Guard
    Graph --> RAG
    Graph --> Mem
    Graph --> Tools
    Graph --> Skills
    Graph --> LLM
    RAG --> Vec
    Vec --> Q
    Graph --> Vec
    LLM --> OAI

    classDef frontend fill:#1e293b,stroke:#64748b,color:#f8fafc
    classDef api fill:#1e1b4b,stroke:#6366f1,color:#f8fafc
    classDef ext fill:#0f172a,stroke:#f59e0b,color:#f8fafc
    class Frontend,Landing,Dash,Client frontend
    class API,Routes,Container,Graph,Guard,LLM,RAG,Tools,Skills,Mem,Vec api
    class External,Q,OAI,FS ext
```

### Backend Component Diagram

```mermaid
flowchart TB
    subgraph Core["Core Layer"]
        Config["config.py<br/>(AppSettings)"]
        Container["container.py<br/>(DI)"]
        Middleware["middleware.py<br/>(X-Request-ID)"]
    end

    subgraph Routes["API Layer"]
        Chat["POST /api/chat"]
        Stream["POST /api/chat/stream"]
        Bench["POST /api/benchmark"]
        Ingest["POST /api/documents/ingest"]
        Health["GET /api/health"]
    end

    subgraph Agent["Agent Layer"]
        Init["initialize<br/>• load history<br/>• input guardrail"]
        Retrieve["retrieve<br/>• vector search<br/>• rerank + filter"]
        Tools["run_tools<br/>• keyword dispatch"]
        Skills["run_skills<br/>• sub-agent dispatch"]
        Ctx["build_context<br/>• token budget<br/>• prompt assembly"]
        Gen["generate<br/>• LLM call<br/>• output guardrail<br/>• grounding check"]
    end

    subgraph Guard["Guardrails"]
        Safety["ContentSafety<br/>(toxicity + injection)"]
        PII["PII Redaction<br/>(email, SSN, key)"]
        Cite["CitationVerifier<br/>(grounding score)"]
        Rel["RelevanceFilter<br/>(score < 0.15)"]
    end

    subgraph Storage["Storage"]
        SQL["ConversationStore<br/>(SQLite)"]
        Qdrant["VectorStore<br/>(Qdrant)"]
        MemStore["InMemoryStore<br/>(test)"]
    end

    subgraph LLM["LLM Providers"]
        LC["LangChainChatClient<br/>(ChatOpenAI)"]
        OR["OpenRouterClient<br/>(httpx)"]
        Echo["EchoLLMClient<br/>(mock)"]
    end

    Routes --> Container
    Container --> Agent
    Init --> Safety
    Init --> PII
    Retrieve --> Rel
    Gen --> Cite
    Gen --> Safety
    Gen --> OR
    Gen --> LC
    Gen --> Echo
    Ctx --> SQL
    Retrieve --> Qdrant
    Retrieve --> MemStore
    Tools --> Calc
    Tools --> Weather
    Tools --> Web

    classDef core fill:#1e1b4b,stroke:#6366f1,color:#f8fafc
    classDef route fill:#312e81,stroke:#818cf8,color:#f8fafc
    classDef agent fill:#1e293b,stroke:#64748b,color:#f8fafc
    classDef guard fill:#4a0e4e,stroke:#e879f9,color:#f8fafc
    classDef storage fill:#0f172a,stroke:#f59e0b,color:#f8fafc
    classDef llm fill:#0c0a1e,stroke:#a855f7,color:#f8fafc
    class Core,Config,Container,Middleware core
    class Routes,Chat,Stream,Bench,Ingest,Health route
    class Agent,Init,Retrieve,Tools,Skills,Ctx,Gen agent
    class Guard,Safety,PII,Cite,Rel guard
    class Storage,SQL,Qdrant,MemStore storage
    class LLM,LC,OR,Echo llm
```

### Frontend Architecture

```mermaid
graph TB
    subgraph Pages["Next.js Pages"]
        Home["/ (Landing Page)<br/>Hero + Feature Cards + Nav Link"]
        Benchmark["/benchmark<br/>BenchmarkDashboard"]
        Health["/api/health<br/>Health Check Endpoint"]
    end

    subgraph Components["React Components"]
        Dashboard["BenchmarkDashboard<br/>• Prompt input<br/>• Side-by-side RAG responses<br/>• MetricBadge grid (6 metrics)<br/>• Winner banner<br/>• JSON output (collapsible)"]
        MetricBadge["MetricBadge<br/>(memoized component)"]
    end

    subgraph Services["Services"]
        APIClient["lib/api.ts<br/>• sendChat()<br/>• runBenchmark()<br/>• request() with AbortController timeout"]
    end

    subgraph Config["Configuration"]
        Styles["globals.css<br/>(hero-grid,<br/>Inter font family)"]
        Layout["layout.tsx<br/>(RootLayout with metadata)"]
    end

    Home --> Dashboard
    Benchmark --> Dashboard
    Dashboard --> APIClient
    Dashboard --> MetricBadge
    APIClient --> BackendAPI["FastAPI Backend (port 8000)"]
    Health --> BackendAPI

    classDef pages fill:#1e293b,stroke:#64748b,color:#f8fafc
    classDef components fill:#1e1b4b,stroke:#6366f1,color:#f8fafc
    classDef services fill:#0f172a,stroke:#f59e0b,color:#f8fafc
    classDef config fill:#0c0a1e,stroke:#a855f7,color:#f8fafc
    class Home,Benchmark,Health pages
    class Dashboard,MetricBadge components
    class APIClient,BackendAPI services
    class Styles,Layout config
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, LangChain, LangGraph |
| Frontend | Next.js 14, React 18, Tailwind CSS |
| Vector DB | Qdrant (with in-memory fallback for tests) |
| Memory | SQLite via aiosqlite |
| LLM | OpenAI / OpenRouter (with EchoLLMClient fallback) |
| Guardrails | Content safety, PII redaction, prompt injection detection |
| Hallucination Reduction | Citation verifier, relevance threshold, confidence scoring |
| Packaging | Docker Compose (backend + frontend + Qdrant) |
| CI | GitHub Actions (ruff, mypy, pytest, Next.js build) |
| Observability | LangSmith tracing on all tests |

## Features

- **AI Agent** with tool calling, memory, and context compression
- **Naive RAG**: sequential retrieve → generate pipeline
- **StreamRAG**: parallel retrieval + streaming generation with background context updates
- **Tools**: Calculator, DateTime, Weather, Web Search, Knowledge Search, Document Search
- **Memory**: SQLite-backed conversation history with automated summarization
- **Context Management**: token budgeting, history trimming, compression
- **Sub-agent / Skill**: ResearchSkill for multi-step analysis
- **Benchmarking**: automated comparison of both paths on latency, tokens, cost, grounding
- **Side-by-side UI**: compare both RAG responses simultaneously
- **Input Guardrails**: content safety (toxicity, prompt injection detection) and PII redaction (emails, SSNs, phones, API keys, IPs, credit cards) at API and graph entry points
- **Output Guardrails**: post-generation toxicity check and citation grounding verification with per-sentence support scoring
- **Hallucination Reduction**: citation verifier computes `grounding_score` and `hallucination_rate` by measuring keyword overlap between LLM output and retrieved chunks; low-relevance chunks filtered via `score_threshold=0.05`
- **Confidence Scoring**: `confidence_score` field on every `ChatResponse`, derived from grounding verification results

## How to Run

### One-command (Docker)

```bash
git clone https://github.com/DIP-RO/Naive-RAG-and-StreamRAG-Benchmarking-Application.git
cd Naive-RAG-and-StreamRAG-Benchmarking-Application
docker compose up --build
```

Then open http://localhost:3000

### Local development

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Run benchmark

```bash
# Start backend first (see above), then:
python benchmark/run.py
```

### Run tests

```bash
cd backend
pytest
```

## Folder Structure

```
.
├── backend/             # FastAPI + agent + RAG pipelines
│   ├── src/app/
│   │   ├── agents/      # Agent orchestration
│   │   ├── api/         # REST routes
│   │   ├── benchmark/   # Benchmark runner
│   │   ├── config/      # App settings
│   │   ├── core/        # DI container, logging, middleware
│   │   ├── memory/      # Conversation store, context manager
│   │   ├── models/      # Pydantic schemas
│   │   ├── naiverag/    # Naive RAG pipeline
│   │   ├── retrieval/   # Vector store, embeddings, chunker, reranker
│   │   ├── services/    # LLM client, tools, guardrails, document ingestion
│   │   ├── skills/      # Sub-agent / skill system
│   │   ├── streamrag/   # StreamRAG pipeline
│   │   ├── tests/       # Pytest test suite
│   │   └── utils/       # Text, time, token counter
│   └── Dockerfile
├── frontend/            # Next.js UI
│   ├── app/             # Pages and layouts
│   ├── components/      # React components
│   └── lib/             # API client
├── documents/           # Example documents for RAG ingestion
├── benchmark/           # Benchmark scripts and test dataset
├── BENCHMARK.md         # Benchmark report
├── docker-compose.yml   # Multi-service orchestration
└── README.md            # This file
```

## Design Decisions

### Why FastAPI?
Async-first Python framework with native OpenAPI docs, Pydantic integration, and production-grade performance.

### Why LangChain + LangGraph?
Provides battle-tested abstractions for LLM interactions, token counting, and chain composition without hiding implementation details.

### Why Qdrant?
Purpose-built vector database with Rust-based performance, async Python client, and Docker-native deployment.

### Why parallel StreamRAG?
StreamRAG starts retrieval immediately in parallel with generation, reducing time-to-first-token by ~65% compared to sequential Naive RAG. Broad retrieval continues in the background for mid-generation context updates.

### Why SQLite for memory?
Zero-dependency, file-based persistence that works everywhere. Good enough for single-server deployments.

### Why async throughout?
All I/O (database, HTTP, LLM calls) is async, enabling high concurrency with minimal resource usage.

### Why heuristic guardrails instead of an LLM-based guard?
Heuristic guardrails (regex patterns for toxicity, injection, PII) have zero latency, zero cost, and no external dependency. They run on every request before the LLM is invoked, providing a fast first line of defense. An LLM-based guard classifier would be more accurate but would add latency and cost proportional to every query. For production, we recommend adding a dedicated guardrail model (e.g., NeMo Guardrails, Guardrails AI) as a second pass.

### Why keyword-overlap for citation grounding?
Computing grounding by measuring keyword overlap between LLM output sentences and retrieved chunk text is fast (no model inference), deterministic, and interpretable. A more accurate approach would use NLI-based entailment or BERTScore, but those introduce latency and cost. The keyword-overlap method catches the most common hallucination pattern — the LLM introducing facts not present in the source material — without requiring an external model.

## Reviewer Test Cases

The following queries exercise all major system components. Run each against both Naive RAG and StreamRAG via the frontend (http://localhost:3000) or API:

| # | Query | Expected Behavior | System Component |
|---|-------|-------------------|-----------------|
| 1 | "What is the capital of France?" | Returns "no data available" message with topic suggestions | Knowledge retrieval (no-data fallback) |
| 2 | "Calculate 2 + 3 * 4" | Returns `14.0` via calculator tool | Calculator tool with operator precedence |
| 3 | "What is 15% of 200?" | Returns `30.0` via calculator tool | Percentage calculator (`X% of Y`) |
| 4 | "What is the square root of 144?" | Returns `12.0` via calculator tool | Square root support |
| 5 | "What time is it right now?" | Returns current UTC timestamp | DateTime tool |
| 6 | "What is the weather like?" | Returns weather JSON with latitude, longitude, temperature | Weather tool (Open-Meteo API) |
| 7 | "Tell me about machine learning" | Returns content from `machine_learning_basics.txt` | RAG retrieval (keyword keyword-overlap) |
| 8 | "How does solar power work?" | Returns content from `renewable_energy.txt` | RAG retrieval (hash-based embedding) |
| 9 | "Who is the CEO of Next Ventures?" | Returns content from `company_overview.txt` — should mention "Sarah Chen" | RAG retrieval (entity resolution) |
| 10 | "My email is test@example.com and SSN is 123-45-6789" | Returns "no data available" (calculator not triggered by SSN pattern); PII redaction active | PII guardrail + calculator false-positive prevention |
| 11 | "Kill all humans" | Returns "no data available"; `flagged` field should be `true` | Input content safety guardrail |
| 12 | "Tell me about the Eiffel Tower" | Returns "no data available" message | Knowledge retrieval (no-data fallback) |

For the full 22-query automated benchmark:
```bash
python benchmark/run.py
```

## Limitations

- **Small document set**: 10 example documents; not representative of production-scale knowledge bases
- **No authentication**: API is open; add API key middleware for production
- **Simple tool routing**: Heuristic keyword matching instead of model-mediated function calling
- **StreamRAG approximated**: Text-only SSE streaming (not voice). Retrieval starts before generation completes
- **No real reranking**: Uses hybrid score (cosine + keyword overlap), not a cross-encoder model
- **No persistence for benchmark runs**: Results are in-memory; not yet stored in Postgres for trend analysis
- **Heuristic guardrails**: Regex-based content safety and PII detection may have false positives/negatives; an LLM-based guard classifier would be more accurate
- **Keyword-overlap grounding**: Citation verification uses token overlap, not semantic entailment; may miss factual errors that use the same vocabulary as source text

## Future Improvements

- Voice input/output with WebSocket streaming
- Model-mediated function calling for tool routing
- Real cross-encoder reranking model
- MCP (Model Context Protocol) integration
- Redis-based conversation memory for multi-instance deployments
- Multi-agent planning and delegation
- Persistent benchmark results in Postgres for trend analysis
- PDF/HTML document ingestion pipeline
- Authentication and rate limiting
- LLM-based guardrail classifier (NeMo Guardrails / Guardrails AI) as second-pass verification
- NLI-based entailment scoring for citation grounding (higher accuracy than keyword overlap)
- Structured output enforcement (JSON Schema) for LLM responses to reduce hallucination surface
