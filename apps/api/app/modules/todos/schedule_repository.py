"""Conditional writes for delayed recurring To-do catch-up and delivery results."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, case, func, or_, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.orm import TodoItem
from app.modules.todos.occurrences import TodoScheduleSnapshot


def _matches(snapshot: TodoScheduleSnapshot) -> ColumnElement[bool]:
    return and_(
        TodoItem.id == snapshot.id,
        TodoItem.user_id == snapshot.user_id,
        TodoItem.content == snapshot.content,
        TodoItem.due_at == snapshot.due_at,
        TodoItem.recurrence_rule == snapshot.recurrence_rule,
        TodoItem.checked == snapshot.checked,
        TodoItem.notification_sent_at == snapshot.notification_sent_at,
    )


async def advance_schedules_if_current(
    session: AsyncSession, advances: list[tuple[TodoScheduleSnapshot, datetime]]
) -> int:
    """Advance a fetched page in one statement without overwriting changed rows; how
    many moved."""
    if not advances:
        return 0
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(TodoItem)
            .where(or_(*(_matches(snapshot) for snapshot, _ in advances)))
            .values(
                due_at=case({snapshot.id: due for snapshot, due in advances}, value=TodoItem.id),
                due_set_at=func.now(),
                notification_sent_at=None,
                email_sent_at=None,
            )
            .execution_options(synchronize_session=False)
        ),
    )
    return result.rowcount


async def stamp_pushed_if_current(
    session: AsyncSession, snapshots: list[TodoScheduleSnapshot], *, sent_at: datetime
) -> int:
    """Stamp a page of pushed reminders sent in one statement; a row changed since it was
    read is left alone. A delivery is not a change to the to-do: ``updated_at`` stays.
    How many were stamped."""
    if not snapshots:
        return 0
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(TodoItem)
            .where(or_(*(_matches(snapshot) for snapshot in snapshots)))
            .values(notification_sent_at=sent_at, updated_at=TodoItem.updated_at)
            .execution_options(synchronize_session=False)
        ),
    )
    return result.rowcount


async def move_due_day_if_current(
    session: AsyncSession, todo_id: UUID, *, was: datetime, to: datetime
) -> bool:
    """Hold one date alone on its day at ``to``; no commit. Whether it moved: one edited
    since it was read (another ``due_at``, or given a time) is left alone. Holding a date
    alone on its day is not an edit: ``updated_at``, which dates a completed row, stays."""
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(TodoItem)
            .where(
                TodoItem.id == todo_id,
                TodoItem.due_at == was,
                TodoItem.due_has_time.is_(False),
            )
            .values(due_at=to, updated_at=TodoItem.updated_at)
            .execution_options(synchronize_session=False)
        ),
    )
    return result.rowcount > 0
