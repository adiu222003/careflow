"""
Health endpoint tests.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "CareFlow API"
    assert "features" in data
    assert "llm" in data["features"]
    assert "email" in data["features"]
    assert "google_calendar" in data["features"]


@pytest.mark.asyncio
async def test_health_features_disabled_in_test(client: AsyncClient) -> None:
    """Confirm feature flags are off in test environment."""
    response = await client.get("/api/v1/health")
    data = response.json()
    assert data["features"]["llm"] is False
    assert data["features"]["email"] is False
    assert data["features"]["google_calendar"] is False
