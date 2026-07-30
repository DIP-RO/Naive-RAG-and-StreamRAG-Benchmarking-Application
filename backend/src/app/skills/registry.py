from __future__ import annotations

from typing import Any

from app.skills.base import Skill, SkillResult


class SkillRegistry:
    def __init__(self, skills: list[Skill]) -> None:
        self._skills = {skill.name: skill for skill in skills}

    def available_skills(self) -> list[str]:
        return list(self._skills.keys())

    async def run(
        self, name: str, query: str, context: dict[str, Any] | None = None
    ) -> SkillResult:
        skill = self._skills[name]
        return await skill.execute(query=query, context=context or {})

    async def run_matching(
        self, query: str, context: dict[str, Any] | None = None
    ) -> list[SkillResult]:
        results: list[SkillResult] = []
        lowered = query.lower()
        for skill in self._skills.values():
            triggers = getattr(skill, "triggers", [skill.name])
            if any(word in lowered for word in triggers):
                results.append(await skill.execute(query=query, context=context or {}))
        return results
