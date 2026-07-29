from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import ChatMessage
from app.utils.token_counter import count_messages, count_tokens


@dataclass(slots=True)
class ContextBudget:
    max_context_tokens: int
    reserved_output_tokens: int

    @property
    def available_tokens(self) -> int:
        return max(1, self.max_context_tokens - self.reserved_output_tokens)


class ContextManager:
    """Trim, compress, and rank context to fit a token budget."""

    def build_prompt_messages(
        self,
        history: list[ChatMessage],
        summary: str | None,
        retrieved_context: str,
        user_message: str,
        budget: ContextBudget,
        model: str,
    ) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        if summary:
            messages.append(ChatMessage(role="system", content=f"Conversation summary:\n{summary}"))
        if retrieved_context:
            messages.append(ChatMessage(role="system", content=f"Retrieved evidence:\n{retrieved_context}"))

        trimmed_history = self._trim_history(history, budget, model=model)
        messages.extend(trimmed_history)
        messages.append(ChatMessage(role="user", content=user_message))
        return messages

    def _trim_history(
        self,
        history: list[ChatMessage],
        budget: ContextBudget,
        model: str,
    ) -> list[ChatMessage]:
        if not history:
            return []
        kept: list[ChatMessage] = []
        spent = 0
        for message in reversed(history):
            tokens = count_tokens(message.content, model=model)
            if spent + tokens > budget.available_tokens // 3:
                break
            kept.append(message)
            spent += tokens
        return list(reversed(kept))

    def context_token_usage(self, messages: list[ChatMessage], model: str) -> int:
        return count_messages([message.content for message in messages], model=model)
