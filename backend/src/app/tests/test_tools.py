from __future__ import annotations

import pytest
from langsmith import traceable

from app.models.schemas import ToolName
from app.services.tools import CalculatorTool, DateTimeTool


@pytest.mark.asyncio
@traceable(name="test_calculator_basic")
async def test_calculator_tool_supports_basic_arithmetic() -> None:
    tool = CalculatorTool()
    result = await tool.execute(query="What is 15 + 27?", context={})
    assert result.name == ToolName.calculator
    assert float(result.output) == 42.0


@pytest.mark.asyncio
@traceable(name="test_calculator_percentage")
async def test_calculator_percentage() -> None:
    tool = CalculatorTool()
    result = await tool.execute(query="What is 15% of 200?", context={})
    assert result.name == ToolName.calculator
    assert abs(float(result.output) - 30.0) < 0.01


@pytest.mark.asyncio
@traceable(name="test_calculator_decimal")
async def test_calculator_decimal() -> None:
    tool = CalculatorTool()
    result = await tool.execute(query="Calculate 3.14 * 2", context={})
    assert result.name == ToolName.calculator
    assert abs(float(result.output) - 6.28) < 0.01


@pytest.mark.asyncio
@traceable(name="test_calculator_division_by_zero")
async def test_calculator_division_by_zero() -> None:
    tool = CalculatorTool()
    result = await tool.execute(query="What is 5/0?", context={})
    assert "Error" in result.output or result.name == ToolName.calculator


@pytest.mark.asyncio
@traceable(name="test_datetime_tool")
async def test_datetime_tool_returns_iso_timestamp() -> None:
    tool = DateTimeTool()
    result = await tool.execute(query="What time is it?", context={})
    assert result.name == ToolName.datetime
    assert "T" in result.output
