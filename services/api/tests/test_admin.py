from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.admin.setup import setup_admin
from tests.conftest import test_engine


@pytest.mark.asyncio
async def test_admin_dashboard_accessible(async_client: AsyncClient) -> None:
    response = await async_client.get("/admin/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_admin_user_view(async_client: AsyncClient) -> None:
    response = await async_client.get("/admin/user/list")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_admin_bot_view(async_client: AsyncClient) -> None:
    response = await async_client.get("/admin/bot/list")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_setup_admin_disabled() -> None:
    dummy_app = FastAPI()
    with patch("app.admin.setup.settings.ADMIN_ENABLED", False):
        result = setup_admin(dummy_app, test_engine)
        assert result is None
