from unittest.mock import AsyncMock, patch

import pytest

from app.main import app, lifespan


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown() -> None:
    mock_engine = AsyncMock()
    with patch("app.main.engine", mock_engine):
        async with lifespan(app):
            pass
        mock_engine.dispose.assert_awaited_once()
