from __future__ import annotations

from app.memory.context_manager import ContextBudget, ContextManager
from app.models.schemas import ChatMessage


def test_context_manager_trims_history_to_budget() -> None:
    manager = ContextManager()
    history = [ChatMessage(role="user", content="one two three four five") for _ in range(10)]
    messages = manager.build_prompt_messages(
        history=history,
        summary="summary",
        retrieved_context="evidence",
        user_message="question",
        budget=ContextBudget(max_context_tokens=200, reserved_output_tokens=50),
        model="gpt-4.1",
    )
    assert messages[0].role == "system"
    assert messages[-1].role == "user"
