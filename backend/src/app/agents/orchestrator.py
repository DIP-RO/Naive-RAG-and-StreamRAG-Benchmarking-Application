from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph
from langsmith import traceable

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

_STREAM_BUFFER_LIMIT = 100_000


class AgentState(TypedDict):
    request: ChatRequest
    conversation_id: str
    request_id: str
    history: list[ChatMessage]
    tool_results: list[Any]
    skill_results: list[Any]
    retrieved_chunks: list[RetrievalChunk]
    reranked: list[RetrievalChunk]
    context_text: str
    summary: str | None
    prompt_messages: list[ChatMessage]
    answer_text: str
    usage: dict[str, int]
    started: float


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
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        graph.add_node("initialize", self._node_initialize)
        graph.add_node("retrieve", self._node_retrieve)
        graph.add_node("run_tools", self._node_run_tools)
        graph.add_node("run_skills", self._node_run_skills)
        graph.add_node("build_context", self._node_build_context)
        graph.add_node("generate", self._node_generate)

        graph.set_entry_point("initialize")
        graph.add_edge("initialize", "retrieve")
        graph.add_edge("initialize", "run_tools")
        graph.add_edge("initialize", "run_skills")
        graph.add_edge("retrieve", "build_context")
        graph.add_edge("run_tools", "build_context")
        graph.add_edge("run_skills", "build_context")
        graph.add_edge("build_context", "generate")
        graph.add_edge("generate", END)

        return graph.compile()

    async def _node_initialize(self, state: AgentState) -> dict[str, Any]:
        request = state["request"]
        conversation_id = state["conversation_id"]
        await self.deps.conversation_store.initialize()
        history = request.history or await self.deps.conversation_store.fetch_history(conversation_id)
        await self.deps.conversation_store.append(conversation_id, ChatMessage(role="user", content=request.message))
        return {"history": history}

    async def _node_retrieve(self, state: AgentState) -> dict[str, Any]:
        request = state["request"]
        chunks = await self.deps.vector_store.search(request.message, limit=self.deps.settings.naive_top_k)
        reranked = self.deps.reranker.rerank(request.message, chunks)
        return {"retrieved_chunks": chunks, "reranked": reranked}

    async def _node_run_tools(self, state: AgentState) -> dict[str, Any]:
        results = await self._maybe_run_tools(state["request"].message)
        return {"tool_results": results}

    async def _node_run_skills(self, state: AgentState) -> dict[str, Any]:
        results = await self.deps.skills.run_matching(state["request"].message, context={})
        return {"skill_results": results}

    async def _node_build_context(self, state: AgentState) -> dict[str, Any]:
        request = state["request"]
        context_text = self._build_context_text(state["reranked"], state["tool_results"], state["skill_results"])
        summary = await self.deps.conversation_store.get_summary(state["conversation_id"])
        prompt_messages = self.deps.context_manager.build_prompt_messages(
            history=state["history"],
            summary=summary.summary if summary else None,
            retrieved_context=context_text,
            user_message=request.message,
            budget=ContextBudget(
                max_context_tokens=request.max_context_tokens or self.deps.settings.max_context_tokens,
                reserved_output_tokens=self.deps.settings.max_output_tokens,
            ),
            model=request.model or self.deps.settings.default_llm_model,
        )
        return {"context_text": context_text, "summary": summary.summary if summary else None, "prompt_messages": prompt_messages}

    async def _node_generate(self, state: AgentState) -> dict[str, Any]:
        request = state["request"]
        answer_text, usage = await self.deps.llm.generate_text(
            state["prompt_messages"],
            model=request.model or self.deps.settings.default_llm_model,
            max_tokens=self.deps.settings.max_output_tokens,
        )
        await self.deps.conversation_store.append(state["conversation_id"], ChatMessage(role="assistant", content=answer_text))
        if count_tokens(state["context_text"]) > 2_000:
            await self.deps.conversation_store.store_summary(state["conversation_id"], self._summarize_locally(state["history"], request.message, answer_text))
        return {"answer_text": answer_text, "usage": usage}

    @traceable(run_type="chain", name="AgentOrchestrator.answer")
    async def answer(self, request: ChatRequest) -> ChatResponse:
        started = perf_counter()
        request_id = str(uuid4())
        conversation_id = request.conversation_id or str(uuid4())

        initial_state: AgentState = {
            "request": request,
            "conversation_id": conversation_id,
            "request_id": request_id,
            "history": [],
            "tool_results": [],
            "skill_results": [],
            "retrieved_chunks": [],
            "reranked": [],
            "context_text": "",
            "summary": None,
            "prompt_messages": [],
            "answer_text": "",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "started": started,
        }

        result = await self._graph.ainvoke(initial_state)
        latency_ms = (perf_counter() - started) * 1000.0

        tool_results = result.get("tool_results", [])
        skill_results = result.get("skill_results", [])
        reranked = result.get("reranked", [])

        return ChatResponse(
            conversation_id=conversation_id,
            mode=request.mode,
            answer=result.get("answer_text", ""),
            citations=reranked,
            tool_calls=self._fmt_tool_results(tool_results) + [{"skill": r.name, "output": r.output} for r in skill_results],
            usage=result.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            latency_ms=latency_ms,
            request_id=request_id,
            trace={"retrieved_chunks": len(reranked), "tools": [r.name.value for r in tool_results if not isinstance(r, Exception)], "skills": [r.name for r in skill_results]},
        )

    @traceable(run_type="chain", name="AgentOrchestrator.stream_answer")
    async def stream_answer(self, request: ChatRequest) -> AsyncIterator[str]:
        started = perf_counter()
        request_id = str(uuid4())
        conversation_id = request.conversation_id or str(uuid4())
        await self.deps.conversation_store.initialize()
        history = request.history or await self.deps.conversation_store.fetch_history(conversation_id)
        await self.deps.conversation_store.append(conversation_id, ChatMessage(role="user", content=request.message))
        yield StreamEvent(type="started", conversation_id=conversation_id, request_id=request_id, payload={"mode": request.mode.value}).model_dump_json()

        initial_task = asyncio.create_task(self.deps.vector_store.search(request.message, limit=self.deps.settings.stream_initial_top_k))
        broad_task = asyncio.create_task(self.deps.vector_store.search(request.message, limit=self.deps.settings.stream_final_top_k))
        tool_task = asyncio.create_task(self._maybe_run_tools(request.message))
        skill_task = asyncio.create_task(self.deps.skills.run_matching(request.message, context={}))

        try:
            initial_chunks = await initial_task
            initial_reranked = self.deps.reranker.rerank(request.message, initial_chunks)
        except Exception as exc:  # noqa: BLE001
            yield StreamEvent(type="error", conversation_id=conversation_id, request_id=request_id, payload={"error": f"Retrieval failed: {exc}"}).model_dump_json()
            return

        try:
            tool_results = await tool_task
        except Exception as exc:  # noqa: BLE001
            tool_results = []
            yield StreamEvent(type="error", conversation_id=conversation_id, request_id=request_id, payload={"warning": f"Tool execution failed: {exc}"}).model_dump_json()

        try:
            skill_results = await skill_task
        except Exception:  # noqa: BLE001
            skill_results = []

        initial_context = self._build_context_text(initial_reranked, tool_results, skill_results)
        summary = await self.deps.conversation_store.get_summary(conversation_id)
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
        buffer_size = 0
        try:
            async for delta in self.deps.llm.stream_text(
                prompt_messages,
                model=request.model or self.deps.settings.default_llm_model,
                max_tokens=self.deps.settings.max_output_tokens,
            ):
                answer_parts.append(delta)
                buffer_size += len(delta)
                if buffer_size > _STREAM_BUFFER_LIMIT:
                    answer_parts = [answer_parts[-1]]
                    buffer_size = len(answer_parts[-1])
                yield StreamEvent(type="delta", conversation_id=conversation_id, request_id=request_id, payload={"text": delta}).model_dump_json()
        except Exception as exc:  # noqa: BLE001
            yield StreamEvent(type="error", conversation_id=conversation_id, request_id=request_id, payload={"error": f"Generation failed: {exc}"}).model_dump_json()
            return

        try:
            broad_chunks = await broad_task
            broad_reranked = self.deps.reranker.rerank(request.message, broad_chunks)
            if len(broad_reranked) > len(initial_reranked):
                yield StreamEvent(
                    type="context_update",
                    conversation_id=conversation_id,
                    request_id=request_id,
                    payload={"new_chunks": [chunk.model_dump() for chunk in broad_reranked[len(initial_reranked):]]},
                ).model_dump_json()
        except Exception:  # noqa: BLE001, S110
            pass

        final_answer = "".join(answer_parts).strip()
        await self.deps.conversation_store.append(conversation_id, ChatMessage(role="assistant", content=final_answer))
        latency_ms = (perf_counter() - started) * 1000.0
        yield StreamEvent(
            type="completed",
            conversation_id=conversation_id,
            request_id=request_id,
            payload={"answer": final_answer, "latency_ms": latency_ms, "tool_calls": self._fmt_tool_results(tool_results) + [{"skill": r.name, "output": r.output} for r in skill_results]},
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

    @staticmethod
    def _build_context_text(chunks: list[RetrievalChunk], tool_results: list[Any], skill_results: list[Any] | None = None) -> str:
        parts: list[str] = []
        for chunk in chunks:
            parts.append(f"[{chunk.title}] {chunk.content}")
        for result in tool_results:
            parts.append(f"[tool:{result.name.value}] {result.output}")
        if skill_results:
            for result in skill_results:
                parts.append(f"[skill:{result.name}] {result.output}")
        return "\n\n".join(parts)

    @staticmethod
    def _fmt_tool_results(results: list[Any]) -> list[dict[str, Any]]:
        return [r.metadata | {"tool": r.name.value, "output": r.output} for r in results if not isinstance(r, Exception)]

    def _summarize_locally(self, history: list[ChatMessage], user_message: str, answer: str) -> str:
        recent = history[-6:]
        recent_text = " | ".join(message.content for message in recent)
        return f"Recent context: {recent_text}\nLatest user query: {user_message}\nLatest answer: {answer[:800]}"
