"""Opt-in transactional email reminders (todo due + learning nudges).

Runs on the worker scheduler only — never on the chat path. Welcome and Pro
receipt emails stay on the Redis jobs stream and are not gated by
``email_reminders_enabled``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import TodoItem, User
from app.repositories.todo_email import TodoEmailSnapshot, mark_email_sent_if_current
from app.services.learning import nudges as learning_nudges
from app.services.notifications import transactional_email as tx_email
from app.services.reminder_timing import (
    MAX_REMINDER_LEAD_MINUTES,
    OVERDUE_MAX_HOURS,
    reminder_title,
    resolve_reminder_lead_minutes,
    should_notify_todo,
)

logger = logging.getLogger(__name__)

LEARNING_EMAIL_REDIS_PREFIX = "recall:email:learning"


@dataclass(frozen=True)
class _TodoEmailDelivery:
    occurrence: TodoEmailSnapshot
    email: str
    name: str | None
    locale: str
    title: str


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
            TodoItem.recurrence_rule.is_(None),
            User.email_reminders_enabled.is_(True),
            (
                (TodoItem.due_at <= window_end)
                | ((TodoItem.due_at < now) & (TodoItem.due_at >= overdue_cutoff))
            ),
        )
    )
    deliveries: list[_TodoEmailDelivery] = []
    for todo, user in result.all():
        if todo.due_at is None or not user.email:
            continue
        try:
            lead = resolve_reminder_lead_minutes(getattr(user, "reminder_lead_minutes", None))
            if not should_notify_todo(todo.due_at, now=now, lead_minutes=lead):
                continue
            deliveries.append(
                _TodoEmailDelivery(
                    occurrence=TodoEmailSnapshot.from_todo(todo),
                    email=user.email,
                    name=user.name,
                    locale=user.locale,
                    title=reminder_title(is_overdue=todo.due_at < now, locale=user.locale),
                )
            )
        except Exception:
            logger.exception("Todo reminder email preparation failed todo_id=%s", todo.id)

    # This worker owns its session. Release the read transaction before provider IO;
    # copy every delivery first because rollback expires ORM rows, including users.
    await session.rollback()
    sent = 0
    for delivery in deliveries:
        occurrence = delivery.occurrence
        try:
            recipient = User(
                id=occurrence.user_id,
                email=delivery.email,
                name=delivery.name,
                locale=delivery.locale,
            )
            ok = await tx_email.send_todo_reminder(
                settings, recipient, title=delivery.title, content=occurrence.content
            )
            if ok:
                await mark_email_sent_if_current(session, occurrence, now)
                await session.commit()
                sent += 1
        except Exception:
            await session.rollback()
            logger.exception("Todo reminder email failed todo_id=%s", occurrence.id)
            continue

    return sent


async def process_learning_nudge_emails(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    effective_now = now or datetime.now(UTC)
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
        now=effective_now,
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
