from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import UserCalendarConnection


async def get_for_user(session: AsyncSession, user_id: UUID) -> UserCalendarConnection | None:
    result = await session.execute(
        select(UserCalendarConnection).where(UserCalendarConnection.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    *,
    user_id: UUID,
    google_email: str,
    refresh_token: str,
    scopes: str,
    calendar_id: str = "primary",
) -> UserCalendarConnection:
    row = await get_for_user(session, user_id)
    if row is None:
        row = UserCalendarConnection(
            user_id=user_id,
            google_email=google_email,
            refresh_token=refresh_token,
            scopes=scopes,
            calendar_id=calendar_id,
        )
        session.add(row)
    else:
        row.google_email = google_email
        row.refresh_token = refresh_token
        row.scopes = scopes
        row.calendar_id = calendar_id
    await session.commit()
    await session.refresh(row)
    return row


async def delete_for_user(session: AsyncSession, user_id: UUID) -> bool:
    row = await get_for_user(session, user_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True
