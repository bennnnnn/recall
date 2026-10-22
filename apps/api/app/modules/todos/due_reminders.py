"""Which dated to-dos a reminder channel owes now: one query for push and email.

Both channels used to write their own copy of the same window, join and checks,
with email's recurring-row filter the one deliberate difference, so a change to
what "due" means had to be made twice. The candidates come in pages ordered by
``(due_at, id)`` over a partial index per channel (migration 0117), so a minute's
cycle reads only rows in the reminder window and stops at its bound; the rest
come next cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import ColumnElement, false, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.orm import PushToken, TodoItem, User
from app.services.reminder_timing import (
    MAX_REMINDER_LEAD_MINUTES,
    OVERDUE_MAX_HOURS,
    in_quiet_hours,
    resolve_reminder_lead_minutes,
    should_notify_todo,
)


@dataclass(frozen=True, slots=True)
class ReminderChannel:
    """What one channel marks when it sends, and who has asked for it."""

    name: str
    sent_at: InstrumentedAttribute[datetime | None]
    opted_in: tuple[ColumnElement[bool], ...]
    include_recurring: bool


PUSH = ReminderChannel(
    name="push",
    sent_at=TodoItem.notification_sent_at,
    opted_in=(
        User.push_notifications_enabled.is_(True),
        User.push_reminders_enabled.is_(True),
        # A user with no device token is left out here: everyone who denied the OS
        # permission sat in every minute's scan for 48 hours.
        select(PushToken.id).where(PushToken.user_id == TodoItem.user_id).exists(),
    ),
    include_recurring=True,
)
# A recurring to-do moves to its next occurrence when pushed; email does not send them.
EMAIL = ReminderChannel(
    name="email",
    sent_at=TodoItem.email_sent_at,
    opted_in=(User.email_reminders_enabled.is_(True), User.email != ""),
    include_recurring=False,
)

PageKey = tuple[datetime, UUID]


async def due_reminder_page(
    session: AsyncSession,
    channel: ReminderChannel,
    *,
    now: datetime,
    after: PageKey | None = None,
    limit: int = 500,
) -> list[tuple[TodoItem, User]]:
    """Open dated to-dos in the window ``[now - 48 h, now + the longest lead]`` the channel
    has not sent, ordered by ``(due_at, id)`` and starting after ``after``.

    ``checked == false()`` renders ``checked = false``, the predicate the partial index
    has; ``IS false`` might not let the planner use it.
    """
    stmt = (
        select(TodoItem, User)
        .join(User, User.id == TodoItem.user_id)
        .where(
            TodoItem.checked == false(),
            TodoItem.due_at.isnot(None),
            channel.sent_at.is_(None),
            TodoItem.due_at >= now - timedelta(hours=OVERDUE_MAX_HOURS),
            TodoItem.due_at <= now + timedelta(minutes=MAX_REMINDER_LEAD_MINUTES),
            *channel.opted_in,
        )
        .order_by(TodoItem.due_at, TodoItem.id)
        .limit(limit)
    )
    if not channel.include_recurring:
        stmt = stmt.where(TodoItem.recurrence_rule.is_(None))
    if after is not None:
        stmt = stmt.where(tuple_(TodoItem.due_at, TodoItem.id) > tuple_(*after))
    return [(todo, user) for todo, user in (await session.execute(stmt)).all()]


def page_key(rows: list[tuple[TodoItem, User]]) -> PageKey | None:
    """Where the next page starts: after the last row of this one."""
    if not rows:
        return None
    last = rows[-1][0]
    if last.due_at is None:
        return None
    return last.due_at, last.id


def is_due_now(todo: TodoItem, user: User, *, now: datetime) -> bool:
    """The user's lead time has come for this to-do and it is not their quiet hours."""
    if todo.due_at is None or in_quiet_hours(user, now=now):
        return False
    lead = resolve_reminder_lead_minutes(user.reminder_lead_minutes)
    return should_notify_todo(todo.due_at, now=now, lead_minutes=lead)


async def tokenless_recurring_overdue(
    session: AsyncSession, *, now: datetime, limit: int = 500
) -> list[tuple[TodoItem, User]]:
    """Overdue recurring to-dos of push users with no device, which push skips.

    Each is moved to its next occurrence so it neither waits forever nor fires late.
    """
    has_token = select(PushToken.id).where(PushToken.user_id == TodoItem.user_id).exists()
    stmt = (
        select(TodoItem, User)
        .join(User, User.id == TodoItem.user_id)
        .where(
            TodoItem.checked == false(),
            TodoItem.due_at.isnot(None),
            TodoItem.notification_sent_at.is_(None),
            TodoItem.recurrence_rule.isnot(None),
            TodoItem.due_at >= now - timedelta(hours=OVERDUE_MAX_HOURS),
            TodoItem.due_at <= now,
            User.push_notifications_enabled.is_(True),
            User.push_reminders_enabled.is_(True),
            ~has_token,
        )
        .order_by(TodoItem.due_at, TodoItem.id)
        .limit(limit)
    )
    return [(todo, user) for todo, user in (await session.execute(stmt)).all()]
