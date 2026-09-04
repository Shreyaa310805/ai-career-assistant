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

from app.core.config import get_settings

settings = get_settings()

_connect_args = {}
if settings.resume_database_url.startswith("sqlite"):
    # allow the aiosqlite connection to be shared across the async test client
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.resume_database_url,
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


# Columns added after the original ISSUE-03 schema was frozen. create_all()
# only creates missing *tables*, so an existing dev database needs each new
# column added explicitly. Every entry must be nullable and additive.
_ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("ats_reports", "score_breakdown", "JSON"),
)


async def init_db() -> None:
    """Create tables if they don't exist, then apply additive column changes.

    For Postgres in real deployments prefer Alembic migrations against
    ISSUE-03's schema; this is kept for standalone/dev/test convenience so an
    existing SQLite file does not have to be deleted after a schema addition.
    """
    from sqlalchemy import inspect, text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _existing_columns(sync_conn, table: str) -> set[str]:
            inspector = inspect(sync_conn)
            if table not in inspector.get_table_names():
                return set()
            return {column["name"] for column in inspector.get_columns(table)}

        for table, column, column_type in _ADDITIVE_COLUMNS:
            present = await conn.run_sync(_existing_columns, table)
            if present and column not in present:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
