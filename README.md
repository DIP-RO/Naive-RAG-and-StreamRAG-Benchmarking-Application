# Naive RAG vs StreamRAG — Benchmarking Application

AI Agent comparing Naive RAG and StreamRAG in a full-stack production system with guardrails, hallucination reduction, and observability.

## Deliverables Checklist

- [x] **Public GitHub repo** with code, README, and benchmark report
- [x] **One-command setup**: `docker compose up --build`
- [x] **README** with architecture, setup, and design decisions
- [x] **Benchmark scripts**: `python benchmark/run.py`
- [x] **Test dataset**: `benchmark/test_set.json` (10 queries with expected answers)
- [x] **Example documents**: `documents/` (5 files for RAG ingestion)
- [x] **Benchmark report**: `BENCHMARK.md`
- [ ] **Video**: 5-min walkthrough (intro, architecture, demo, tradeoffs)

## Architecture

### Backend Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend (Next.js 14)"]
        UI["Landing Page<br/>(/)"]
        Benchmark["Benchmark Dashboard<br/>(/benchmark)"]
        API["API Client<br/>(lib/api.ts)"]
    end

    subgraph Backend["Backend (FastAPI)"]
        Routes["API Routes<br/>(routes.py)"]
        Container["DI Container<br/>(container.py)"]

        subgraph Agent["Agent Layer (LangGraph)"]
            Graph["StateGraph<br/>(orchestrator.py)"]
            Nodes["Nodes:<br/>• initialize<br/>• retrieve<br/>• run_tools<br/>• run_skills<br/>• build_context<br/>• generate"]
            Memory["MemorySaver<br/>(checkpointer)"]
        end

        subgraph RAG["RAG Pipelines"]
            Naive["Naive RAG<br/>retrieve → generate<br/>(sequential)"]
            Stream["StreamRAG<br/>parallel retrieve +<br/>streaming generate"]
        end

        subgraph Retrieval["Retrieval Layer"]
            Embeddings["Embeddings<br/>• OpenAI text-embedding-3-small<br/>• Deterministic (fallback)"]
            VectorDB["Vector Store<br/>• Qdrant (prod)<br/>• InMemory (test)"]
            Chunker["Chunker<br/>(sentence-aware,<br/>overlap)"]
            Reranker["HybridReranker<br/>(cosine + keyword)"]
        end

        subgraph Guardrails["Guardrails & Hallucination Reduction"]
            Safety["ContentSafetyChecker<br/>(toxicity + injection)"]
            PII["PIIRedactor<br/>(email, SSN, API keys)"]
            Citation["CitationVerifier<br/>(sentence-level grounding)"]
            Relevance["RelevanceFilter<br/>(score < 0.15 dropped)"]
        end

        subgraph Tools["Tool Registry"]
            Calc["CalculatorTool<br/>(safe eval with<br/>AST parsing)"]
            DT["DateTimeTool"]
            Weather["WeatherTool<br/>(Open-Meteo API)"]
            Web["WebSearchTool"]
            DocSearch["DocumentSearchTool"]
            KnowSearch["KnowledgeSearchTool"]
        end

        subgraph Skills["Skills (Sub-agents)"]
            Research["ResearchSkill<br/>(multi-step analysis)"]
            SkillReg["SkillRegistry"]
        end

        subgraph Memory["Memory & Context"]
            ConvStore["ConversationStore<br/>(SQLite - persistent<br/>connection pool)"]
            CtxMgr["ContextManager<br/>(token budget,<br/>history trimming)"]
        end

        subgraph LLM["LLM Providers"]
            LangChainClient["LangChainChatClient<br/>(ChatOpenAI wrapper)"]
            ORClient["OpenRouterClient<br/>(direct httpx)"]
            EchoClient["EchoLLMClient<br/>(test fallback)"]
        end
    end

    subgraph Monitoring["Observability"]
        LS["LangSmith<br/>(@traceable decorators)"]
        LG["LangGraph<br/>(StateGraph tracing)"]
    end

    subgraph Data["Data Stores"]
        Qdrant["Qdrant v1.11.4<br/>(vector database)"]
        PG["PostgreSQL 16<br/>(available)"]
        FS["File System<br/>(documents/)"]
    end

    UI --> Routes
    Benchmark --> Routes
    API --> Routes
    Routes --> Container
    Container --> Agent
    Container --> RAG
    Container --> Retrieval
    Container --> Tools
    Container --> Skills
    Container --> Memory
    Container --> LLM
    Container --> Guardrails

    Graph --> Nodes
    Nodes -. "input guardrails" .-> Guardrails
    Nodes -. "output guardrails & grounding" .-> Guardrails
    Graph --> Memory
    Naive --> Graph
    Stream --> Graph
    Embeddings --> LangChainClient
    Embeddings --> EchoClient
    LangChainClient --> ORClient
    LangChainClient --> EchoClient

    VectorDB --> Qdrant
    VectorDB --> FS
    Research --> LangChainClient
    Research --> EchoClient

    Routes -- "@traceable" --> LS
    Graph -- "LangGraph tracing" --> LG
    ConvStore --> PG

    classDef frontend fill:#1e293b,stroke:#64748b,color:#f8fafc
    classDef backend fill:#1e1b4b,stroke:#6366f1,color:#f8fafc
    classDef storage fill:#0f172a,stroke:#f59e0b,color:#f8fafc
    classDef llm fill:#0c0a1e,stroke:#a855f7,color:#f8fafc
    classDef observability fill:#064e3b,stroke:#34d399,color:#f8fafc
    classDef guardrails fill:#4a0e4e,stroke:#e879f9,color:#f8fafc
    classDef data fill:#451a03,stroke:#fb923c,color:#f8fafc
    class Frontend,UI,Benchmark,API frontend
    class Backend,Routes,Container,Agent,Graph,Nodes,Memory,RAG,Naive,Stream,Retrieval,Embeddings,VectorDB,Chunker,Reranker,Tools,Calc,DT,Weather,Web,DocSearch,KnowSearch,Skills,Research,SkillReg,ConvStore,CtxMgr backend
    class Guardrails,Safety,PII,Citation,Relevance guardrails
    class LLM,LangChainClient,ORClient,EchoClient llm
    class Monitoring,LS,LG observability
    class Data,Qdrant,PG,FS data
    class Qdrant,PG,FS storage
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
- **Hallucination Reduction**: citation verifier computes `grounding_score` and `hallucination_rate` by measuring keyword overlap between LLM output and retrieved chunks; low-relevance chunks filtered via `score_threshold=0.15`
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

## Limitations

- **Small document set**: 5 example documents; not representative of production-scale knowledge bases
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
