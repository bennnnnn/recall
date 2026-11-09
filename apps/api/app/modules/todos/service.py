"""Public todo operations for other product modules.

This module does not import chat, so live talk can call it without a circular
import.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem
from app.modules.todos import repository as todos_repo
from app.modules.todos.due_day import same_day_in
from app.modules.todos.schedule_repository import move_due_days

logger = logging.getLogger(__name__)


async def list_owned_todos(
    session: AsyncSession, user_id: UUID, *, limit: int, offset: int = 0
) -> list[TodoItem]:
    """Read a page of a user's to-dos without advancing recurrence."""
    return await todos_repo.list_for_user(session, user_id, limit=limit, offset=offset)


async def todos_for_export(
    session: AsyncSession, user_id: UUID, *, after_id: UUID | None, limit: int
) -> list[TodoItem]:
    """A page of the user's to-dos after ``after_id`` by id (the data export); no
    recurrence is advanced, and a to-do deleted meanwhile skips no other."""
    return await todos_repo.list_after_id(session, user_id, limit=limit, cursor=after_id)


async def keep_date_only_days(
    session: AsyncSession, user_id: UUID, *, old_timezone: str | None, new_timezone: str | None
) -> None:
    """Hold each date-only to-do on its day when the user's zone changes; no commit.

    A date alone is held at the start of its day on the user's clock, and is overdue when
    that day ends there. Left at the old zone's midnight, a flight from New York to Los
    Angeles showed it on the day before and called it overdue a day early.
    """
    rows = await todos_repo.list_date_only(session, user_id)
    moves = {
        row.id: same_day_in(row.due_at, old_timezone, new_timezone)
        for row in rows
        if row.due_at is not None
    }
    try:
        # A savepoint: a same-titled to-do already at the new midnight leaves the days
        # where they were rather than refusing the new zone.
        async with session.begin_nested():
            await move_due_days(session, moves)
    except IntegrityError:
        logger.warning("Date-only to-dos kept their old zone's days user_id=%s", user_id)


async def delete_user_rows(session: AsyncSession, user_id: UUID) -> None:
    """Every to-do of a deleted account; no commit (``account.lifecycle``)."""
    await todos_repo.delete_all_for_user(session, user_id)
