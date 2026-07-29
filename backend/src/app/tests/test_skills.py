from __future__ import annotations

import pytest

from app.services.llm import EchoLLMClient
from app.skills.registry import SkillRegistry
from app.skills.research import ResearchSkill


@pytest.mark.asyncio
async def test_research_skill_executes_with_echo_llm() -> None:
    llm = EchoLLMClient()
    skill = ResearchSkill(llm=llm, model="gpt-4.1")
    result = await skill.execute("test query", context={})
    assert result.name == "research"
    assert "test query" in result.output


@pytest.mark.asyncio
async def test_skill_registry_runs_matching() -> None:
    llm = EchoLLMClient()
    skill = ResearchSkill(llm=llm, model="gpt-4.1")
    registry = SkillRegistry([skill])
    results = await registry.run_matching("research this topic", context={})
    assert len(results) == 1
    assert results[0].name == "research"


@pytest.mark.asyncio
async def test_skill_registry_no_match() -> None:
    llm = EchoLLMClient()
    skill = ResearchSkill(llm=llm, model="gpt-4.1")
    registry = SkillRegistry([skill])
    results = await registry.run_matching("hello", context={})
    assert results == []


@pytest.mark.asyncio
async def test_skill_registry_available_skills() -> None:
    llm = EchoLLMClient()
    skill = ResearchSkill(llm=llm, model="gpt-4.1")
    registry = SkillRegistry([skill])
    assert "research" in registry.available_skills()
