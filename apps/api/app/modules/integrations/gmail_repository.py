from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import UserGmailConnection


async def get_for_user(session: AsyncSession, user_id: UUID) -> UserGmailConnection | None:
    result = await session.execute(
        select(UserGmailConnection).where(UserGmailConnection.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    *,
    user_id: UUID,
    google_email: str,
    refresh_token: str,
    scopes: str,
) -> UserGmailConnection:
    row = await get_for_user(session, user_id)
    if row is None:
        row = UserGmailConnection(
            user_id=user_id,
            google_email=google_email,
            refresh_token=refresh_token,
            scopes=scopes,
        )
        session.add(row)
    else:
        row.google_email = google_email
        row.refresh_token = refresh_token
        row.scopes = scopes
    await session.commit()
    await session.refresh(row)
    return row


async def update_last_sync(session: AsyncSession, user_id: UUID) -> None:
    from datetime import UTC, datetime

    row = await get_for_user(session, user_id)
    if row is None:
        return
    row.last_sync_at = datetime.now(UTC)
    await session.commit()


async def delete_for_user(session: AsyncSession, user_id: UUID) -> bool:
    row = await get_for_user(session, user_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def list_due(
    session: AsyncSession,
    *,
    cutoff: datetime,
    limit: int,
) -> list[UserGmailConnection]:
    """Connections that have never synced or last synced before ``cutoff``."""
    result = await session.execute(
        select(UserGmailConnection)
        .where(
            or_(
                UserGmailConnection.last_sync_at.is_(None),
                UserGmailConnection.last_sync_at < cutoff,
            )
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_all(session: AsyncSession) -> list[UserGmailConnection]:
    result = await session.execute(select(UserGmailConnection))
    return list(result.scalars().all())
