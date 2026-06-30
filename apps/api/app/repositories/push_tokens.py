from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import PushToken


async def upsert(
    session: AsyncSession,
    *,
    user_id: UUID,
    expo_push_token: str,
    platform: str,
    device_id: str | None = None,
) -> PushToken:
    result = await session.execute(
        select(PushToken).where(PushToken.expo_push_token == expo_push_token)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = PushToken(
            user_id=user_id,
            expo_push_token=expo_push_token,
            platform=platform,
            device_id=device_id,
        )
        session.add(row)
    else:
        row.user_id = user_id
        row.platform = platform
        row.device_id = device_id
    await session.commit()
    await session.refresh(row)
    return row


async def delete_token(session: AsyncSession, user_id: UUID, expo_push_token: str) -> bool:
    result = await session.execute(
        delete(PushToken).where(
            PushToken.user_id == user_id,
            PushToken.expo_push_token == expo_push_token,
        )
    )
    await session.commit()
    return (result.rowcount or 0) > 0


async def delete_by_token(session: AsyncSession, expo_push_token: str) -> int:
    """Delete a push token by its string (used for pruning invalid tokens)."""
    result = await session.execute(
        delete(PushToken).where(PushToken.expo_push_token == expo_push_token)
    )
    await session.commit()
    return int(result.rowcount or 0)


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[PushToken]:
    result = await session.execute(select(PushToken).where(PushToken.user_id == user_id))
    return list(result.scalars().all())
