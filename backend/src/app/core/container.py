from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from qdrant_client import AsyncQdrantClient

from app.agents.orchestrator import AgentDependencies, AgentOrchestrator
from app.benchmark.runner import BenchmarkRunner
from app.core.config import AppSettings
from app.memory.context_manager import ContextManager
from app.memory.conversation_store import ConversationStore
from app.naiverag.pipeline import NaiveRagPipeline
from app.retrieval.chunker import Chunker
from app.retrieval.embeddings import DeterministicEmbeddingProvider, OpenAIEmbeddingProvider
from app.retrieval.reranker import HybridReranker
from app.retrieval.vector_store import InMemoryVectorStore, QdrantVectorStore, VectorStoreProtocol
from app.services.documents import DocumentIngestionService
from app.services.guardrails import GuardrailService
from app.services.llm import LLMFactory
from app.services.tools import (
    CalculatorTool,
    DateTimeTool,
    DocumentSearchTool,
    KnowledgeSearchTool,
    ToolRegistry,
    WeatherTool,
    WebSearchTool,
)
from app.skills.registry import SkillRegistry
from app.skills.research import ResearchSkill
from app.streamrag.pipeline import StreamRagPipeline

logger = logging.getLogger(__name__)


@dataclass
class AppContainer:
    settings: AppSettings
    conversation_store: ConversationStore
    vector_store: VectorStoreProtocol
    orchestrator: AgentOrchestrator
    naive_pipeline: NaiveRagPipeline
    stream_pipeline: StreamRagPipeline
    benchmark_runner: BenchmarkRunner
    document_ingestion: DocumentIngestionService
    _qdrant_client: AsyncQdrantClient | None = None
    _resources: list[Any] = field(default_factory=list)

    async def close(self) -> None:
        await self.conversation_store.close()
        if self._qdrant_client is not None:
            await self._qdrant_client.close()
        for resource in self._resources:
            if hasattr(resource, "aclose"):
                await resource.aclose()
            elif hasattr(resource, "close"):
                await resource.close()
        from app.utils.http_client import SHARED_HTTP_CLIENT

        await SHARED_HTTP_CLIENT.aclose()


async def build_container(settings: AppSettings) -> AppContainer:
    embeddings = (
        OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key, model=settings.default_embedding_model
        )
        if settings.openai_api_key
        else DeterministicEmbeddingProvider()
    )
    vector_store: VectorStoreProtocol
    qdrant_client: AsyncQdrantClient | None = None
    if settings.environment == "test":
        vector_store = InMemoryVectorStore(embeddings)
    else:
        try:
            qdrant_client = AsyncQdrantClient(url=settings.qdrant_url, timeout=2.0)
            qdrant_store = QdrantVectorStore(qdrant_client, settings.qdrant_collection, embeddings)
            await qdrant_store.ensure_collection(
                vector_size=getattr(embeddings, "dimensions", 1536)
            )
            vector_store = qdrant_store
        except Exception:  # noqa: BLE001
            logger.warning(
                "qdrant_unavailable_using_in_memory_store",
                extra={"qdrant_url": settings.qdrant_url},
            )
            vector_store = InMemoryVectorStore(embeddings)

    conversation_store = ConversationStore(settings.sqlite_path)

    tools = ToolRegistry(
        [
            CalculatorTool(),
            DateTimeTool(),
            WebSearchTool(),
            WeatherTool(),
            KnowledgeSearchTool(search_fn=_noop_search),
            DocumentSearchTool(search_fn=vector_store.search),
        ]
    )
    llm = LLMFactory.build(settings)
    skills = SkillRegistry([ResearchSkill(llm=llm, model=settings.default_llm_model)])
    guardrails = GuardrailService()
    orchestrator = AgentOrchestrator(
        AgentDependencies(
            settings=settings,
            llm=llm,
            conversation_store=conversation_store,
            vector_store=vector_store,
            context_manager=ContextManager(),
            reranker=HybridReranker(),
            tools=tools,
            skills=skills,
            guardrails=guardrails,
        )
    )
    naive_pipeline = NaiveRagPipeline(orchestrator=orchestrator)
    stream_pipeline = StreamRagPipeline(orchestrator=orchestrator)
    benchmark_runner = BenchmarkRunner(
        naive=naive_pipeline, stream=stream_pipeline, guardrails=guardrails
    )
    document_ingestion = DocumentIngestionService(Chunker(), vector_store)

    return AppContainer(
        settings=settings,
        conversation_store=conversation_store,
        vector_store=vector_store,
        orchestrator=orchestrator,
        naive_pipeline=naive_pipeline,
        stream_pipeline=stream_pipeline,
        benchmark_runner=benchmark_runner,
        document_ingestion=document_ingestion,
        _qdrant_client=qdrant_client,
    )


async def _noop_search(query: str) -> str:
    return f"No knowledge base configured for query: {query}"
