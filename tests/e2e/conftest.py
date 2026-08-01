"""Reset global SQLAlchemy engine between async tests (loop isolation)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
async def _reset_db_engine():
    import packages.db.session as sess

    async def _clear() -> None:
        if sess._engine is not None:
            await sess._engine.dispose()
        sess._engine = None
        sess._session_factory = None

    await _clear()
    yield
    await _clear()
