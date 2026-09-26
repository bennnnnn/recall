"""Bounded, owner-scoped practice history for account exports."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import LearningPracticeEvent


async def list_page(
    session: AsyncSession,
    user_id: UUID,
    *,
    through: datetime,
    limit: int,
    after: tuple[datetime, UUID] | None = None,
) -> list[LearningPracticeEvent]:
    stmt = select(LearningPracticeEvent).where(
        LearningPracticeEvent.user_id == user_id,
        LearningPracticeEvent.occurred_at <= through,
    )
    if after is not None:
        stmt = stmt.where(
            tuple_(LearningPracticeEvent.occurred_at, LearningPracticeEvent.id) > after
        )
    result = await session.execute(
        stmt.order_by(LearningPracticeEvent.occurred_at, LearningPracticeEvent.id).limit(limit)
    )
    return list(result.scalars().all())
