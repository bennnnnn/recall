from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    """Atomically increment daily usage (safe under concurrent finalizes)."""
    stmt = pg_insert(UsageDaily).values(
        user_id=user_id,
        date=day,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[UsageDaily.user_id, UsageDaily.date],
        set_={
            "input_tokens": UsageDaily.input_tokens + stmt.excluded.input_tokens,
            "output_tokens": UsageDaily.output_tokens + stmt.excluded.output_tokens,
        },
    )
    await session.execute(stmt)
    if commit:
        await session.commit()
    else:
        await session.flush()
    usage = await get_for_date(session, user_id, day)
    if usage is None:  # pragma: no cover — upsert always leaves a row
        raise RuntimeError("usage_daily upsert did not produce a row")
    if commit:
        await session.refresh(usage)
    return usage


async def get_total_for_date(session: AsyncSession, user_id: UUID, day: date) -> int:
    result = await session.execute(
        select(UsageDaily).where(UsageDaily.user_id == user_id, UsageDaily.date == day)
    )
    usage = result.scalar_one_or_none()
    if not usage:
        return 0
    return usage.input_tokens + usage.output_tokens
