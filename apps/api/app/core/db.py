from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.database_url import pool_recycle_seconds_for_url, prepare_asyncpg_url


class Base(DeclarativeBase):
    pass


settings = get_settings()
_db_url, _connect_args = prepare_asyncpg_url(
    settings.database_url,
    prefer_neon_pooler=settings.database_prefer_neon_pooler,
)
engine = create_async_engine(
    _db_url,
    echo=False,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    # Fail fast under burst instead of the 30s default — a stalled checkout
    # should surface as a fast error/retry, not a 30s TTFT hang.
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=pool_recycle_seconds_for_url(_db_url),
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def warmup_db_pool() -> None:
    """Open one connection at startup so the first chat turn skips cold connect."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
