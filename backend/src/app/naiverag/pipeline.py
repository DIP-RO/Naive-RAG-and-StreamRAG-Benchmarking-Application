from __future__ import annotations

from dataclasses import dataclass

from app.agents.orchestrator import AgentOrchestrator
from app.models.schemas import ChatRequest, ChatResponse


@dataclass(slots=True)
class NaiveRagPipeline:
    orchestrator: AgentOrchestrator

    async def run(self, request: ChatRequest) -> ChatResponse:
        return await self.orchestrator.answer(request)
