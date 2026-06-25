from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User


async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_google_sub(session: AsyncSession, google_sub: str) -> User | None:
    result = await session.execute(select(User).where(User.google_sub == google_sub))
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    google_sub: str,
    email: str,
    name: str | None,
    avatar_url: str | None,
) -> User:
    user = User(google_sub=google_sub, email=email, name=name, avatar_url=avatar_url)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update(session: AsyncSession, user: User, **fields) -> User:
    for key, value in fields.items():
        if value is not None or isinstance(value, bool):
            if hasattr(user, key):
                setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user
