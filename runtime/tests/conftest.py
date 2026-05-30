"""Pytest fixtures.

Uses the configured Postgres (DATABASE_URL) with a NullPool engine + a dependency
override, which keeps connections from being reused across pytest-asyncio event
loops. Tables are created once at import (idempotent with the Alembic migration).
"""

from __future__ import annotations

import asyncio
import os

# Defaults for local dev so the suite runs without an .env file present.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://tyndale:tyndale@127.0.0.1:5432/tyndale"
)
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("NODE_ENV", "development")
# Phase 2K.2: rate limiting OFF by default so the broader suite (which fires many
# requests) isn't throttled. test_hardening.py turns it on per-test.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.db.models  # noqa: E402,F401  — register tables on Base.metadata
from app.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402

_engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
_Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_session():
    async with _Session() as session:
        yield session


app.dependency_overrides[get_session] = _override_get_session


def _init_db() -> None:
    async def _go() -> None:
        async with _engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            await conn.run_sync(Base.metadata.create_all)
        await _engine.dispose()

    asyncio.run(_go())


_init_db()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_app_engine():
    """Dispose the app's engine after each test.

    Routes/orchestrator/tools use app.db.base.AsyncSessionLocal (the default-
    pool engine) directly, not the NullPool dependency override above.
    pytest-asyncio gives each test its own event loop, so a pooled connection
    opened in one test's loop is bound to that (now-closed) loop and explodes
    with 'RuntimeError: Event loop is closed' when the next test reuses it.
    Disposing after each test forces a fresh connection bound to the next
    test's loop. Test-only — no production impact.
    """
    yield
    from app.db.base import engine as app_engine

    await app_engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
