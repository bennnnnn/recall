"""Opt-in transactional email reminders (todo due + learning nudges).

Runs on the worker scheduler only — never on the chat path. Welcome and Pro
receipt emails stay on the Redis jobs stream and are not gated by
``email_reminders_enabled``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import TodoItem, User
from app.services import learning_nudges
from app.services import transactional_email as tx_email
from app.services.reminder_timing import (
    MAX_REMINDER_LEAD_MINUTES,
    OVERDUE_MAX_HOURS,
    resolve_reminder_lead_minutes,
    should_notify_todo,
)

logger = logging.getLogger(__name__)

LEARNING_EMAIL_REDIS_PREFIX = "recall:email:learning"


async def process_todo_reminder_emails(
    session: AsyncSession,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(UTC)
    window_end = now + timedelta(minutes=MAX_REMINDER_LEAD_MINUTES)
    overdue_cutoff = now - timedelta(hours=OVERDUE_MAX_HOURS)

    result = await session.execute(
        select(TodoItem, User)
        .join(User, User.id == TodoItem.user_id)
        .where(
            TodoItem.checked.is_(False),
            TodoItem.due_at.isnot(None),
            TodoItem.email_sent_at.is_(None),
            User.email_reminders_enabled.is_(True),
            (
                (TodoItem.due_at <= window_end)
                | ((TodoItem.due_at < now) & (TodoItem.due_at >= overdue_cutoff))
            ),
        )
    )
    rows = list(result.all())
    if not rows:
        return 0

    sent = 0
    for todo, user in rows:
        if todo.due_at is None or not user.email:
            continue
        lead = resolve_reminder_lead_minutes(getattr(user, "reminder_lead_minutes", None))
        if not should_notify_todo(todo.due_at, now=now, lead_minutes=lead):
            continue
        is_overdue = todo.due_at < now
        title = "Overdue reminder" if is_overdue else "Reminder"
        ok = await tx_email.send_todo_reminder(settings, user, title=title, content=todo.content)
        if ok:
            todo.email_sent_at = now
            sent += 1

    if sent:
        await session.commit()
    return sent


async def process_learning_nudge_emails(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    _ = now
    result = await session.execute(select(User).where(User.email_reminders_enabled.is_(True)))
    users = list(result.scalars().all())
    if not users:
        return 0

    picks = await learning_nudges.collect_learning_nudge_picks(
        session,
        redis,
        users,
        learning_hour=settings.push_learning_hour,
        redis_prefix=LEARNING_EMAIL_REDIS_PREFIX,
        require_email=True,
    )

    sent = 0
    for pick in picks:
        try:
            ok = await tx_email.send_learning_nudge(settings, pick.user, body=pick.body)
            if ok:
                sent += 1
            else:
                await redis.delete(pick.redis_key)
        except Exception:
            logger.exception("Learning nudge email failed user_id=%s", pick.user.id)
            try:
                await redis.delete(pick.redis_key)
            except Exception:
                logger.exception("Failed to release learning email lock user_id=%s", pick.user.id)
            continue

    return sent


async def run_email_reminder_cycle(session: AsyncSession, redis: Redis, settings: Settings) -> int:
    if not settings.email_enabled or not settings.email_reminders_scheduler_enabled:
        return 0
    now = datetime.now(UTC)
    todo_count = await process_todo_reminder_emails(session, settings, now=now)
    learning_count = await process_learning_nudge_emails(session, redis, settings, now=now)
    return todo_count + learning_count
