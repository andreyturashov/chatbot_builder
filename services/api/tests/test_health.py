from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["service"] == "Chatbot API"


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Chatbot API"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_db_health_check_connected(async_client: AsyncClient) -> None:
    with patch("app.api.v1.endpoints.health.check_db_connection", return_value=(True, None)):
        response = await async_client.get("/api/v1/health/db")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["error"] is None


@pytest.mark.asyncio
async def test_db_health_check_disconnected(async_client: AsyncClient) -> None:
    with patch(
        "app.api.v1.endpoints.health.check_db_connection",
        return_value=(False, "Connection refused"),
    ):
        response = await async_client.get("/api/v1/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "disconnected"
        assert data["error"] == "Connection refused"
