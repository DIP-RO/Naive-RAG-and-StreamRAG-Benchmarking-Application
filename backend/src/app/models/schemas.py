from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RagMode(str, Enum):
    naive = "naive"
    stream = "stream"


class ToolName(str, Enum):
    calculator = "calculator"
    web_search = "web_search"
    knowledge_search = "knowledge_search"
    document_search = "document_search"
    datetime = "datetime"
    weather = "weather"


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    content: str
    score: float = 0.0
    source: str = "vector"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    mode: RagMode = RagMode.naive
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    tools_enabled: list[ToolName] = Field(default_factory=list)
    model: str | None = None
    max_context_tokens: int | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    mode: RagMode
    answer: str
    citations: list[RetrievalChunk] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float
    request_id: str
    trace: dict[str, Any] = Field(default_factory=dict)
    grounding_score: float | None = None
    hallucination_rate: float | None = None
    confidence_score: float | None = None
    flagged: bool = False
    guardrails: dict[str, Any] = Field(default_factory=dict)


class StreamEvent(BaseModel):
    type: str
    conversation_id: str
    request_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    trials: int = 3
    model: str | None = None


class IngestDocumentRequest(BaseModel):
    file_path: str


class BenchmarkRecord(BaseModel):
    mode: RagMode
    latency_ms: float
    time_to_first_token_ms: float | None = None
    embedding_time_ms: float = 0.0
    retrieval_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    memory_bytes: int = 0
    failures: int = 0
    hallucination_rate: float | None = None
    grounding_score: float | None = None


class BenchmarkResponse(BaseModel):
    records: list[BenchmarkRecord]
    winner: RagMode
    summary: dict[str, Any] = Field(default_factory=dict)
