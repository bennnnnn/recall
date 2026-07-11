from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import SuggestedReminder


async def list_pending_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    limit: int = 100,
) -> list[SuggestedReminder]:
    result = await session.execute(
        select(SuggestedReminder)
        .where(
            SuggestedReminder.user_id == user_id,
            SuggestedReminder.status == "pending",
        )
        .order_by(SuggestedReminder.due_at.asc().nulls_last(), SuggestedReminder.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession, reminder_id: UUID, user_id: UUID
) -> SuggestedReminder | None:
    result = await session.execute(
        select(SuggestedReminder).where(
            SuggestedReminder.id == reminder_id,
            SuggestedReminder.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_by_message_id(
    session: AsyncSession, user_id: UUID, gmail_message_id: str
) -> SuggestedReminder | None:
    result = await session.execute(
        select(SuggestedReminder).where(
            SuggestedReminder.user_id == user_id,
            SuggestedReminder.gmail_message_id == gmail_message_id,
        )
    )
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    user_id: UUID,
    gmail_message_id: str,
    title: str,
    due_at: datetime | None,
    notes: str | None,
    confidence: float,
    source_snippet: str | None,
) -> SuggestedReminder:
    row = SuggestedReminder(
        user_id=user_id,
        gmail_message_id=gmail_message_id,
        title=title,
        due_at=due_at,
        notes=notes,
        confidence=confidence,
        source_snippet=source_snippet,
        status="pending",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def mark_added(
    session: AsyncSession, row: SuggestedReminder, todo_id: UUID
) -> SuggestedReminder:
    row.status = "added"
    row.todo_id = todo_id
    await session.commit()
    await session.refresh(row)
    return row


async def mark_dismissed(session: AsyncSession, row: SuggestedReminder) -> SuggestedReminder:
    row.status = "dismissed"
    await session.commit()
    await session.refresh(row)
    return row


async def delete_for_user(session: AsyncSession, user_id: UUID) -> int:
    stmt = delete(SuggestedReminder).where(SuggestedReminder.user_id == user_id)
    result = cast(CursorResult[Any], await session.execute(stmt))
    await session.commit()
    return int(result.rowcount or 0)
