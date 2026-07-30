from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langsmith import traceable

from app.main import app


@pytest.mark.asyncio
@traceable(name="test_health_endpoint")
async def test_health_endpoint_registers() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "environment" in data
