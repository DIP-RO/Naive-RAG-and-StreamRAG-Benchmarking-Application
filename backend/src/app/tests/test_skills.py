from __future__ import annotations

import pytest
from langsmith import traceable

from app.services.llm import EchoLLMClient
from app.skills.registry import SkillRegistry
from app.skills.research import ResearchSkill


@pytest.mark.asyncio
@traceable(name="test_skill_research")
async def test_research_skill_executes_with_echo_llm() -> None:
    skill = ResearchSkill(llm=EchoLLMClient())
    result = await skill.execute(query="Tell me about RAG", context={})
    assert result.name == "research"
    assert "RAG" in result.output


@pytest.mark.asyncio
@traceable(name="test_skill_registry_matching")
async def test_skill_registry_runs_matching() -> None:
    registry = SkillRegistry([ResearchSkill(llm=EchoLLMClient())])
    results = await registry.run_matching("I want to research AI", context={})
    assert len(results) >= 1
    assert results[0].name == "research"


@pytest.mark.asyncio
@traceable(name="test_skill_registry_no_match")
async def test_skill_registry_no_match() -> None:
    registry = SkillRegistry([ResearchSkill(llm=EchoLLMClient())])
    results = await registry.run_matching("Hello world", context={})
    assert len(results) == 0


@pytest.mark.asyncio
@traceable(name="test_skill_registry_available")
async def test_skill_registry_available_skills() -> None:
    registry = SkillRegistry([ResearchSkill(llm=EchoLLMClient())])
    skills = registry.available_skills()
    assert "research" in skills
