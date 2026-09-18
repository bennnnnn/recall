"""Automations CRUD + the scheduler's due-query. Mirrors repositories/todos.py."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Automation


async def create(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    prompt: str,
    frequency: str,
    next_run_at: datetime,
    kind: str = "generic",
    config_json: str | None = None,
    commit: bool = True,
) -> Automation:
    automation = Automation(
        user_id=user_id,
        chat_id=chat_id,
        prompt=prompt.strip(),
        frequency=frequency,
        next_run_at=next_run_at,
        status="active",
        kind=kind,
        config_json=config_json,
    )
    session.add(automation)
    if commit:
        await session.commit()
        await session.refresh(automation)
    else:
        await session.flush()
    return automation


async def get_by_id(session: AsyncSession, automation_id: UUID, user_id: UUID) -> Automation | None:
    result = await session.execute(
        select(Automation).where(Automation.id == automation_id, Automation.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_job_search_for_user(session: AsyncSession, user_id: UUID) -> Automation | None:
    result = await session.execute(
        select(Automation)
        .where(Automation.user_id == user_id, Automation.kind == "job_search")
        .order_by(Automation.created_at.desc(), Automation.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    limit: int = 100,
    kind: str | None = None,
) -> list[Automation]:
    stmt = select(Automation).where(Automation.user_id == user_id)
    if kind is not None:
        stmt = stmt.where(Automation.kind == kind)
    result = await session.execute(
        stmt.order_by(Automation.created_at.desc(), Automation.id.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def count_active_for_user(
    session: AsyncSession, user_id: UUID, *, kind: str | None = None
) -> int:
    stmt = select(Automation).where(
        Automation.user_id == user_id,
        Automation.status == "active",
    )
    if kind is not None:
        stmt = stmt.where(Automation.kind == kind)
    result = await session.execute(stmt)
    return len(result.scalars().all())


async def list_due(
    session: AsyncSession, *, cutoff: datetime, limit: int = 100
) -> list[Automation]:
    """Active automations whose next_run_at has arrived, soonest first."""
    result = await session.execute(
        select(Automation)
        .where(Automation.status == "active", Automation.next_run_at <= cutoff)
        .order_by(Automation.next_run_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update(
    session: AsyncSession, automation: Automation, *, commit: bool = True, **fields: object
) -> Automation:
    for key, value in fields.items():
        if hasattr(automation, key):
            setattr(automation, key, value)
    if commit:
        await session.commit()
        await session.refresh(automation)
    return automation


async def delete_by_id(session: AsyncSession, automation_id: UUID, user_id: UUID) -> bool:
    automation = await get_by_id(session, automation_id, user_id)
    if automation is None:
        return False
    await session.delete(automation)
    await session.commit()
    return True
