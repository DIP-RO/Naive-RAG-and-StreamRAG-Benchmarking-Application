from __future__ import annotations

from dataclasses import dataclass, field

from app.models.schemas import ChatMessage
from app.services.llm import LLMClient
from app.skills.base import SkillResult


@dataclass(slots=True)
class ResearchSkill:
    llm: LLMClient
    name: str = "research"
    description: str = "Multi-step research analysis using retrieval and synthesis"
    triggers: list[str] = field(
        default_factory=lambda: ["research", "analyze", "investigate", "deep dive", "tell me about"]
    )
    model: str = "gpt-4.1"

    async def execute(self, query: str, context: dict[str, str]) -> SkillResult:
        analysis_prompt = ChatMessage(
            role="system",
            content=(
                "You are a research analyst. Break down the user's question into sub-questions, "
                "answer each concisely using the provided context, then synthesize a final answer. "
                "Be thorough and cite specific evidence."
            ),
        )
        context_text = context.get("retrieved_context", "")
        context_msg = (
            ChatMessage(role="system", content=f"Available evidence:\n{context_text}")
            if context_text
            else None
        )
        user_msg = ChatMessage(role="user", content=query)

        messages = [analysis_prompt]
        if context_msg:
            messages.append(context_msg)
        messages.append(user_msg)

        answer, usage = await self.llm.generate_text(messages, model=self.model, max_tokens=1500)
        return SkillResult(
            name=self.name,
            output=answer,
            metadata={
                "model": self.model,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
        )
