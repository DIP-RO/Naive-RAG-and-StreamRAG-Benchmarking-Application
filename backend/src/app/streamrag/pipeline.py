from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.agents.orchestrator import AgentOrchestrator
from app.models.schemas import ChatRequest


@dataclass(slots=True)
class StreamRagPipeline:
    orchestrator: AgentOrchestrator

    async def run(self, request: ChatRequest) -> AsyncIterator[str]:
        async for event in self.orchestrator.stream_answer(request):
            yield event
