from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.database_url import prepare_asyncpg_url


class Base(DeclarativeBase):
    pass


settings = get_settings()
_db_url, _connect_args = prepare_asyncpg_url(settings.database_url)
engine = create_async_engine(
    _db_url,
    echo=False,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=10,
    pool_recycle=300,
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
