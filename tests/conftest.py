"""Shared pytest fixtures and markers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"

# Dedicated local test DB — keeps pytest off the app `underwrite` database.
_DEFAULT_TEST_DB = (
    "postgresql+asyncpg://underwrite:underwrite@localhost:5432/underwrite_test"
)


def _apply_test_database_url() -> None:
    """Prefer TEST_DATABASE_URL; else default underwrite_test (not app DB)."""
    test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if test_url:
        os.environ["DATABASE_URL"] = test_url
        return
    # Only override when caller did not already point DATABASE_URL at *_test*
    current = os.environ.get("DATABASE_URL", "")
    if "underwrite_test" in current:
        return
    if not current or current.endswith("/underwrite") or "/underwrite?" in current:
        os.environ["DATABASE_URL"] = _DEFAULT_TEST_DB


def pytest_configure(config: pytest.Config) -> None:
    _apply_test_database_url()
    # Clear settings cache after env mutation (import may have happened earlier)
    try:
        from packages.config import get_settings

        get_settings.cache_clear()
    except Exception:
        pass

    config.addinivalue_line("markers", "unit: fast isolated tests (default)")
    config.addinivalue_line(
        "markers", "integration: API + Postgres (skipped if DB unreachable)"
    )
    config.addinivalue_line(
        "markers", "e2e: full investigation pipeline (skipped if DB unreachable)"
    )


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def test_database_url() -> str:
    _apply_test_database_url()
    return os.environ.get("DATABASE_URL", _DEFAULT_TEST_DB)


@pytest.fixture(autouse=True)
def _deterministic_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep package-level tests offline-friendly unless a test overrides."""
    _apply_test_database_url()
    monkeypatch.setenv("DATABASE_URL", os.environ["DATABASE_URL"])
    monkeypatch.setenv("OSINT_MODE", os.getenv("OSINT_MODE", "fixture"))
    monkeypatch.setenv("LLM_PROVIDER", os.getenv("LLM_PROVIDER", "heuristic"))
    from packages.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _db_reachable() -> bool:
    try:
        import asyncio

        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        _apply_test_database_url()
        from packages.config import get_settings

        get_settings.cache_clear()
        url = get_settings().database_url

        async def _ping() -> None:
            engine = create_async_engine(url, pool_pre_ping=True)
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            finally:
                await engine.dispose()

        asyncio.run(_ping())
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def require_postgres() -> None:
    _apply_test_database_url()
    if not _db_reachable():
        pytest.skip(
            "Test Postgres not reachable. Run: ./scripts/setup_test_db.sh "
            f"(expected DATABASE_URL={os.environ.get('DATABASE_URL', _DEFAULT_TEST_DB)})"
        )
