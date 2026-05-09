"""Async session factory.

Single engine per process; sessions are short-lived and scoped to a request
or a unit of work. Tests override `get_session_factory` via FastAPI deps.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from inbox_agent.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    settings = get_settings()
    url = settings.database_url
    # SQLite (used in tests) doesn't support sized pools; Postgres does.
    if url.startswith("sqlite"):
        return create_async_engine(url, echo=False)
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a session, commit on success, rollback on error."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
