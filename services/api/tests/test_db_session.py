from unittest.mock import MagicMock, patch

import pytest

from app.db.session import check_db_connection, get_db
from tests.conftest import test_engine


@pytest.mark.asyncio
async def test_get_db_yields_session() -> None:
    session_gen = get_db()
    session = await anext(session_gen)
    assert session is not None
    with pytest.raises(StopAsyncIteration):
        await anext(session_gen)


@pytest.mark.asyncio
async def test_get_db_handles_exception() -> None:
    session_gen = get_db()
    session = await anext(session_gen)
    assert session is not None
    with pytest.raises(RuntimeError, match="DB error during request"):
        await session_gen.athrow(RuntimeError("DB error during request"))


@pytest.mark.asyncio
async def test_check_db_connection_success() -> None:
    with patch("app.db.session.engine", test_engine):
        is_connected, error = await check_db_connection()
        assert is_connected is True
        assert error is None


@pytest.mark.asyncio
async def test_check_db_connection_failure() -> None:
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = ConnectionRefusedError("Database is offline")

    with patch("app.db.session.engine", mock_engine):
        is_connected, error = await check_db_connection()
        assert is_connected is False
        assert "Database is offline" in str(error)
