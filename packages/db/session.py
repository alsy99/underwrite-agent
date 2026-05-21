from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.config import get_settings
from packages.db.models import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine, _session_factory


async def init_db() -> None:
    engine, _ = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    _, factory = _get_engine()
    async with factory() as session:
        yield session
