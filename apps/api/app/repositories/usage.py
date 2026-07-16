from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import UsageDaily


async def get_for_date(session: AsyncSession, user_id: UUID, day: date) -> UsageDaily | None:
    return await session.get(UsageDaily, {"user_id": user_id, "date": day})


async def add_tokens(
    session: AsyncSession,
    user_id: UUID,
    day: date,
    *,
    input_tokens: int,
    output_tokens: int,
    commit: bool = True,
) -> UsageDaily:
    usage = await get_for_date(session, user_id, day)
    if usage is None:
        usage = UsageDaily(user_id=user_id, date=day, input_tokens=0, output_tokens=0)
        session.add(usage)
    usage.input_tokens = (usage.input_tokens or 0) + input_tokens
    usage.output_tokens = (usage.output_tokens or 0) + output_tokens
    if commit:
        await session.commit()
        await session.refresh(usage)
    else:
        await session.flush()
    return usage


async def get_total_for_date(session: AsyncSession, user_id: UUID, day: date) -> int:
    result = await session.execute(
        select(UsageDaily).where(UsageDaily.user_id == user_id, UsageDaily.date == day)
    )
    usage = result.scalar_one_or_none()
    if not usage:
        return 0
    return usage.input_tokens + usage.output_tokens
