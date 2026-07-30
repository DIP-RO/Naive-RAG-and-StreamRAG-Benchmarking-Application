from __future__ import annotations

import ast
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.models.schemas import ToolName


@dataclass(slots=True)
class ToolResult:
    name: ToolName
    output: str
    metadata: dict[str, Any]


class Tool(Protocol):
    name: ToolName

    async def execute(self, *, query: str, context: dict[str, Any]) -> ToolResult: ...


class CalculatorTool:
    name = ToolName.calculator

    async def execute(self, *, query: str, context: dict[str, Any]) -> ToolResult:
        try:
            expression = self._extract_expression(query)
            value = self._safe_eval(expression)
            return ToolResult(
                name=self.name, output=str(value), metadata={"expression": expression}
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                name=self.name,
                output=f"Error: {exc}",
                metadata={"expression": query, "error": str(exc)},
            )

    @staticmethod
    def _extract_expression(text: str) -> str:
        percentage_match = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE
        )
        if percentage_match:
            val, total = float(percentage_match.group(1)), float(percentage_match.group(2))
            return f"{val}*{total}/100"
        match = re.search(
            r"[-+]?\d+(?:\.\d+)?\s*[\+\-\*/%]\s*\d+(?:\.\d+)?(?:\s*[\+\-\*/%]\s*\d+(?:\.\d+)?)*",
            text,
        )
        if match:
            expr = match.group(0).replace("%", "/100*")
            return expr
        return text

    def _safe_eval(self, expression: str) -> float:
        node = ast.parse(expression, mode="eval")
        return float(self._eval_node(node.body))

    def _eval_node(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ValueError("Division by zero")
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right
            if isinstance(node.op, ast.Mod):
                return left % right
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._eval_node(node.operand)
        raise ValueError("Unsupported expression")


class DateTimeTool:
    name = ToolName.datetime

    async def execute(self, *, query: str, context: dict[str, Any]) -> ToolResult:
        current = datetime.now(UTC).isoformat()
        return ToolResult(name=self.name, output=current, metadata={"timezone": "UTC"})


class KnowledgeSearchTool:
    name = ToolName.knowledge_search

    def __init__(self, search_fn: Callable[[str], Awaitable[str]]) -> None:
        self.search_fn = search_fn

    async def execute(self, *, query: str, context: dict[str, Any]) -> ToolResult:
        result = await self.search_fn(query)
        return ToolResult(name=self.name, output=result, metadata={"query": query})


class DocumentSearchTool:
    name = ToolName.document_search

    def __init__(self, search_fn: Callable[..., Awaitable[Any]]) -> None:
        self.search_fn = search_fn

    async def execute(self, *, query: str, context: dict[str, Any]) -> ToolResult:
        chunks = await self.search_fn(query)
        output = "\n\n".join(f"[{chunk.title}] {chunk.content}" for chunk in chunks)
        return ToolResult(name=self.name, output=output, metadata={"chunks": len(chunks)})


class WeatherTool:
    name = ToolName.weather

    async def execute(self, *, query: str, context: dict[str, Any]) -> ToolResult:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": 37.7749,
                    "longitude": -122.4194,
                    "current": "temperature_2m,wind_speed_10m",
                },
            )
            response.raise_for_status()
        return ToolResult(name=self.name, output=response.text, metadata={"provider": "open-meteo"})


class WebSearchTool:
    name = ToolName.web_search

    def __init__(self, endpoint: str | None = None, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.api_key = api_key

    async def execute(self, *, query: str, context: dict[str, Any]) -> ToolResult:
        if not self.endpoint:
            return ToolResult(
                name=self.name,
                output=f"Web search not configured for: {query}",
                metadata={"configured": False},
            )
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(self.endpoint, params={"q": query}, headers=headers)
            response.raise_for_status()
            payload = response.json()
        return ToolResult(name=self.name, output=str(payload), metadata={"configured": True})


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def available_tools(self) -> list[ToolName]:
        return list(self._tools.keys())

    async def run(
        self, name: ToolName, query: str, context: dict[str, Any] | None = None
    ) -> ToolResult:
        tool = self._tools[name]
        return await tool.execute(query=query, context=context or {})

    async def run_many(
        self, requests: list[tuple[ToolName, str]], context: dict[str, Any] | None = None
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        for name, query in requests:
            try:
                result = await self.run(name, query, context=context)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                results.append(
                    ToolResult(name=name, output=f"Error: {exc}", metadata={"error": str(exc)})
                )
        return results
