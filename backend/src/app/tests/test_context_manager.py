from __future__ import annotations

import pytest
from langsmith import traceable

from app.memory.context_manager import ContextBudget, ContextManager
from app.models.schemas import ChatMessage


@pytest.mark.asyncio
@traceable(name="test_context_manager_trim")
async def test_context_manager_trims_history_to_budget() -> None:
    manager = ContextManager()
    history = [ChatMessage(role="user", content=f"Message number {i}") for i in range(20)]
    budget = ContextBudget(max_context_tokens=200, reserved_output_tokens=50)
    trimmed = manager._trim_history(history, budget, model="gpt-4.1")
    assert len(trimmed) <= len(history)
    assert all(isinstance(msg, ChatMessage) for msg in trimmed)
