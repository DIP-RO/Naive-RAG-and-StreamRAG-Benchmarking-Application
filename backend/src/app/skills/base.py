from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class SkillResult:
    name: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Skill(Protocol):
    name: str
    description: str

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        ...
