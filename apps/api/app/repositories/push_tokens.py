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
    elif row.user_id == user_id:
        # Same user re-registering — refresh platform/device metadata.
        row.platform = platform
        row.device_id = device_id
    else:
        # The token is currently bound to a different account. This is the
        # device-transferred-accounts case (sign out, sign in as someone else on
        # the same device). Drop the stale binding and create a fresh row for the
        # current user so the previous owner stops receiving this device's
        # pushes. Reassigning in place would also work, but a clean row avoids
        # carrying over the previous user's platform/device metadata.
        await session.delete(row)
        await session.flush()
        row = PushToken(
            user_id=user_id,
            expo_push_token=expo_push_token,
            platform=platform,
            device_id=device_id,
        )
        session.add(row)
    if device_id:
        await delete_stale_tokens_for_device(
            session,
            user_id=user_id,
            device_id=device_id,
            keep_expo_push_token=expo_push_token,
        )
    await session.commit()
    await session.refresh(row)
    return row


async def delete_stale_tokens_for_device(
    session: AsyncSession,
    *,
    user_id: UUID,
    device_id: str,
    keep_expo_push_token: str,
) -> int:
    """Remove rotated Expo tokens for the same physical device."""
    result = await session.execute(
        delete(PushToken).where(
            PushToken.user_id == user_id,
            PushToken.device_id == device_id,
            PushToken.expo_push_token != keep_expo_push_token,
        )
    )
    return int(result.rowcount or 0)


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


async def list_for_users(session: AsyncSession, user_ids: list[UUID]) -> list[PushToken]:
    """Batched list_for_user — one query across many users instead of one per user."""
    if not user_ids:
        return []
    result = await session.execute(select(PushToken).where(PushToken.user_id.in_(user_ids)))
    return list(result.scalars().all())
