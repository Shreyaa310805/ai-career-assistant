"""
Async SQLAlchemy engine/session setup.

Defaults to SQLite (aiosqlite) so the module runs with no external DB
server. Swap DATABASE_URL to a Postgres/asyncpg DSN (Supabase or otherwise)
for integration/production — no code changes required.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    # allow the aiosqlite connection to be shared across the async test client
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args=_connect_args,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create tables if they don't exist. For Postgres in real deployments
    prefer Alembic migrations against ISSUE-03's schema; this is kept for
    standalone/dev/test convenience."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
