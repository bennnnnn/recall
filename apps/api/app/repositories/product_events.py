from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProductEvent


async def create_batch(
    session: AsyncSession,
    events: Sequence[ProductEvent],
    *,
    commit: bool = True,
) -> None:
    session.add_all(events)
    if commit:
        await session.commit()
    else:
        await session.flush()


async def list_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    limit: int,
) -> list[ProductEvent]:
    result = await session.execute(
        select(ProductEvent)
        .where(ProductEvent.user_id == user_id)
        .order_by(ProductEvent.recorded_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
