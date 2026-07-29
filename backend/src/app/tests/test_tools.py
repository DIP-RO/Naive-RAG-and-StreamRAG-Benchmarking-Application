from __future__ import annotations

import pytest

from app.services.tools import CalculatorTool, DateTimeTool


@pytest.mark.asyncio
async def test_calculator_tool_supports_basic_arithmetic() -> None:
    result = await CalculatorTool().execute(query="2 + 3 * 4", context={})
    assert result.output == "14.0"


@pytest.mark.asyncio
async def test_datetime_tool_returns_iso_timestamp() -> None:
    result = await DateTimeTool().execute(query="now", context={})
    assert "T" in result.output
