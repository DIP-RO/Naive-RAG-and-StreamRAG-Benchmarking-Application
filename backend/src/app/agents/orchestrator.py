from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from app.core.config import AppSettings
from app.memory.context_manager import ContextBudget, ContextManager
from app.memory.conversation_store import ConversationStore
from app.models.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    RetrievalChunk,
    StreamEvent,
)
from app.retrieval.reranker import HybridReranker
from app.retrieval.vector_store import VectorStoreProtocol
from app.services.llm import LLMClient
from app.services.tools import ToolName, ToolRegistry
from app.skills.registry import SkillRegistry
from app.utils.token_counter import count_tokens


@dataclass(slots=True)
class AgentDependencies:
    settings: AppSettings
    llm: LLMClient
    conversation_store: ConversationStore
    vector_store: VectorStoreProtocol
    context_manager: ContextManager
    reranker: HybridReranker
    tools: ToolRegistry
    skills: SkillRegistry


class AgentOrchestrator:
    def __init__(self, deps: AgentDependencies) -> None:
        self.deps = deps

    async def answer(self, request: ChatRequest) -> ChatResponse:
        request_id = str(uuid4())
        conversation_id = request.conversation_id or str(uuid4())
        started = asyncio.get_running_loop().time()
        await self.deps.conversation_store.initialize()
        history = request.history or await self.deps.conversation_store.fetch_history(conversation_id)
        await self.deps.conversation_store.append(conversation_id, ChatMessage(role="user", content=request.message))

        tool_results = await self._maybe_run_tools(request.message)
        skill_results = await self.deps.skills.run_matching(request.message, context={})
        retrieved_chunks = await self.deps.vector_store.search(request.message, limit=self.deps.settings.naive_top_k)
        reranked = self.deps.reranker.rerank(request.message, retrieved_chunks)
        context_text = self._build_context_text(reranked, tool_results, skill_results)
        summary = (await self.deps.conversation_store.get_summary(conversation_id))
        prompt_messages = self.deps.context_manager.build_prompt_messages(
            history=history,
            summary=summary.summary if summary else None,
            retrieved_context=context_text,
            user_message=request.message,
            budget=ContextBudget(
                max_context_tokens=request.max_context_tokens or self.deps.settings.max_context_tokens,
                reserved_output_tokens=self.deps.settings.max_output_tokens,
            ),
            model=request.model or self.deps.settings.default_llm_model,
        )
        answer_text, usage = await self.deps.llm.generate_text(
            prompt_messages,
            model=request.model or self.deps.settings.default_llm_model,
            max_tokens=self.deps.settings.max_output_tokens,
        )
        await self.deps.conversation_store.append(conversation_id, ChatMessage(role="assistant", content=answer_text))
        if count_tokens(context_text) > 2_000:
            await self.deps.conversation_store.store_summary(conversation_id, self._summarize_locally(history, request.message, answer_text))
        latency_ms = (asyncio.get_running_loop().time() - started) * 1000.0
        return ChatResponse(
            conversation_id=conversation_id,
            mode=request.mode,
            answer=answer_text,
            citations=reranked,
            tool_calls=[result.metadata | {"tool": result.name.value, "output": result.output} for result in tool_results] + [{"skill": r.name, "output": r.output} for r in skill_results],
            usage=usage,
            latency_ms=latency_ms,
            request_id=request_id,
            trace={"retrieved_chunks": len(reranked), "tools": [result.name.value for result in tool_results], "skills": [r.name for r in skill_results]},
        )

    async def stream_answer(self, request: ChatRequest) -> AsyncIterator[str]:
        request_id = str(uuid4())
        conversation_id = request.conversation_id or str(uuid4())
        started = asyncio.get_running_loop().time()
        await self.deps.conversation_store.initialize()
        history = request.history or await self.deps.conversation_store.fetch_history(conversation_id)
        await self.deps.conversation_store.append(conversation_id, ChatMessage(role="user", content=request.message))
        yield StreamEvent(type="started", conversation_id=conversation_id, request_id=request_id, payload={"mode": request.mode.value}).model_dump_json()

        initial_task = asyncio.create_task(self.deps.vector_store.search(request.message, limit=self.deps.settings.stream_initial_top_k))
        broad_task = asyncio.create_task(self.deps.vector_store.search(request.message, limit=self.deps.settings.stream_final_top_k))
        tool_task = asyncio.create_task(self._maybe_run_tools(request.message))
        skill_task = asyncio.create_task(self.deps.skills.run_matching(request.message, context={}))

        initial_chunks = await initial_task
        initial_reranked = self.deps.reranker.rerank(request.message, initial_chunks)
        tool_results = await tool_task
        skill_results = await skill_task
        initial_context = self._build_context_text(initial_reranked, tool_results, skill_results)
        summary = (await self.deps.conversation_store.get_summary(conversation_id))
        prompt_messages = self.deps.context_manager.build_prompt_messages(
            history=history,
            summary=summary.summary if summary else None,
            retrieved_context=initial_context,
            user_message=request.message,
            budget=ContextBudget(
                max_context_tokens=request.max_context_tokens or self.deps.settings.max_context_tokens,
                reserved_output_tokens=self.deps.settings.max_output_tokens,
            ),
            model=request.model or self.deps.settings.default_llm_model,
        )
        yield StreamEvent(
            type="retrieval",
            conversation_id=conversation_id,
            request_id=request_id,
            payload={"chunks": [chunk.model_dump() for chunk in initial_reranked]},
        ).model_dump_json()

        answer_parts: list[str] = []
        async for delta in self.deps.llm.stream_text(
            prompt_messages,
            model=request.model or self.deps.settings.default_llm_model,
            max_tokens=self.deps.settings.max_output_tokens,
        ):
            answer_parts.append(delta)
            yield StreamEvent(type="delta", conversation_id=conversation_id, request_id=request_id, payload={"text": delta}).model_dump_json()

        broad_chunks = await broad_task
        broad_reranked = self.deps.reranker.rerank(request.message, broad_chunks)
        if len(broad_reranked) > len(initial_reranked):
            yield StreamEvent(
                type="context_update",
                conversation_id=conversation_id,
                request_id=request_id,
                payload={"new_chunks": [chunk.model_dump() for chunk in broad_reranked[len(initial_reranked):]]},
            ).model_dump_json()

        final_answer = "".join(answer_parts).strip()
        await self.deps.conversation_store.append(conversation_id, ChatMessage(role="assistant", content=final_answer))
        latency_ms = (asyncio.get_running_loop().time() - started) * 1000.0
        yield StreamEvent(
            type="completed",
            conversation_id=conversation_id,
            request_id=request_id,
            payload={"answer": final_answer, "latency_ms": latency_ms, "tool_calls": [result.metadata | {"tool": result.name.value, "output": result.output} for result in tool_results] + [{"skill": r.name, "output": r.output} for r in skill_results]},
        ).model_dump_json()

    async def _maybe_run_tools(self, message: str) -> list[Any]:
        requested: list[tuple[ToolName, str]] = []
        lowered = message.lower()
        if any(symbol in lowered for symbol in ["+", "-", "*", "/", "calculate", "compute"]):
            requested.append((ToolName.calculator, message))
        if any(word in lowered for word in ["time", "date", "today", "now"]):
            requested.append((ToolName.datetime, message))
        if any(word in lowered for word in ["weather", "forecast"]):
            requested.append((ToolName.weather, message))
        if any(word in lowered for word in ["search", "web", "latest"]):
            requested.append((ToolName.web_search, message))
        if not requested:
            return []
        return await self.deps.tools.run_many(requested, context={"query": message})

    def _build_context_text(self, chunks: list[RetrievalChunk], tool_results: list[Any], skill_results: list[Any] | None = None) -> str:
        parts = []
        for chunk in chunks:
            parts.append(f"[{chunk.title}] {chunk.content}")
        for result in tool_results:
            parts.append(f"[tool:{result.name.value}] {result.output}")
        if skill_results:
            for result in skill_results:
                parts.append(f"[skill:{result.name}] {result.output}")
        return "\n\n".join(parts)

    def _summarize_locally(self, history: list[ChatMessage], user_message: str, answer: str) -> str:
        recent = history[-6:]
        recent_text = " | ".join(message.content for message in recent)
        return f"Recent context: {recent_text}\nLatest user query: {user_message}\nLatest answer: {answer[:800]}"
