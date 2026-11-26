"""Opt-in transactional email reminders for dated to-dos.

Runs on the worker scheduler only — never on the chat path. Welcome and Pro
receipt emails stay on the Redis jobs stream and are not gated by
``email_reminders_enabled``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aio import gather_or_cancel
from app.core.config import Settings
from app.gateways.email_gateway import EmailOutcome, EmailResult
from app.models.orm import User
from app.modules.notifications import transactional_email as tx_email
from app.modules.notifications.send_backoff import SendBackoff, occurrence_key
from app.modules.todos import (
    EMAIL_REMINDERS,
    TodoEmailSnapshot,
    due_reminder_page,
    is_due_now,
    mark_reminder_emailed,
    reminder_page_key,
)
from app.services.reminder_timing import reminder_title

logger = logging.getLogger(__name__)

# Due to-dos read per page; a cycle reads pages until its time budget
# (``reminder_cycle_budget_seconds``) and the rest come next minute.
EMAIL_PAGE_ROWS = 200


@dataclass(frozen=True)
class _TodoEmailDelivery:
    occurrence: TodoEmailSnapshot
    email: str
    name: str | None
    locale: str
    title: str


async def _page_deliveries(
    session: AsyncSession, *, now: datetime, after: tuple[datetime, UUID] | None
) -> tuple[list[_TodoEmailDelivery], tuple[datetime, UUID] | None]:
    rows = await due_reminder_page(
        session, EMAIL_REMINDERS, now=now, after=after, limit=EMAIL_PAGE_ROWS
    )
    deliveries: list[_TodoEmailDelivery] = []
    for todo, user in rows:
        try:
            if todo.due_at is None or not is_due_now(todo, user, now=now):
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
    next_after = reminder_page_key(rows) if len(rows) >= EMAIL_PAGE_ROWS else None
    return deliveries, next_after


async def process_todo_reminder_emails(
    session: AsyncSession,
    settings: Settings,
    *,
    now: datetime | None = None,
    keep_lock: Callable[[], Awaitable[bool]] | None = None,
    backoff: SendBackoff | None = None,
) -> int:
    """Send the due reminder emails, a page at a time, marking each batch right after its
    sends.

    ``keep_lock`` refreshes the cycle's lock before each batch; once it fails, the cycle
    stops so a peer that took the lock does not send the same reminders. Pages follow
    while due reminders remain, for ``reminder_cycle_budget_seconds``. ``backoff`` holds
    a reminder whose send failed for now; one waiting out its hold is passed by.
    """
    now = now or datetime.now(UTC)
    stop_at = time.monotonic() + settings.reminder_cycle_budget_seconds
    sent = 0
    after: tuple[datetime, UUID] | None = None
    while True:
        deliveries, after = await _page_deliveries(session, now=now, after=after)
        # This worker owns its session. Release the read transaction before provider IO;
        # every delivery is copied first because rollback expires ORM rows.
        await session.rollback()
        held = await backoff.held([_key(d) for d in deliveries]) if backoff else set()
        due = [delivery for delivery in deliveries if _key(delivery) not in held]
        # A few at once, at most that many a second (the provider's rate limit): one at a
        # time, a cycle's sends waited on each other's round trip.
        rate = max(1, settings.email_reminder_sends_per_second)
        for start in range(0, len(due), rate):
            if keep_lock is not None and not await keep_lock():
                logger.warning("Email reminder cycle lost its lock; stopping")
                return sent
            began = time.monotonic()
            sent += await _send_batch(session, settings, due[start : start + rate], now, backoff)
            if start + rate < len(due):
                await asyncio.sleep(max(0.0, 1.0 - (time.monotonic() - began)))
        if after is None:
            break
        if time.monotonic() >= stop_at:
            logger.info("Email reminder cycle used its time budget; the rest go next cycle")
            break
    return sent


def _key(delivery: _TodoEmailDelivery) -> str:
    return occurrence_key(delivery.occurrence.id, delivery.occurrence.due_at)


def _idempotency_key(delivery: _TodoEmailDelivery) -> str:
    """The same for every send of one occurrence: Resend mails it once."""
    return f"todo-reminder/{_key(delivery)}"


async def _send_batch(
    session: AsyncSession,
    settings: Settings,
    batch: list[_TodoEmailDelivery],
    now: datetime,
    backoff: SendBackoff | None,
) -> int:
    """Send ``batch`` side by side, then mark each one that went out (the session is used
    by one coroutine at a time); how many were sent."""
    results = await gather_or_cancel(*(_send(settings, d, backoff) for d in batch))
    sent = 0
    for delivery, result in zip(batch, results, strict=True):
        if result is None:
            continue
        if result.outcome is EmailOutcome.REJECTED or result.sent:
            # Refused for good (a bad address): stamped as handled, so it is not sent
            # again every minute until it ages out two days later.
            await _mark(session, delivery.occurrence, now)
        sent += int(result.sent)
    return sent


async def _send(
    settings: Settings, delivery: _TodoEmailDelivery, backoff: SendBackoff | None
) -> EmailResult | None:
    """Send one reminder; None when the send raised (logged, and tried next cycle)."""
    occurrence = delivery.occurrence
    try:
        recipient = User(
            id=occurrence.user_id,
            email=delivery.email,
            name=delivery.name,
            locale=delivery.locale,
        )
        result = await tx_email.send_todo_reminder(
            settings,
            recipient,
            title=delivery.title,
            content=occurrence.content,
            idempotency_key=_idempotency_key(delivery),
        )
        if result.outcome is EmailOutcome.RETRY and backoff is not None:
            await backoff.hold(_key(delivery), at_least=result.retry_after)
    except Exception:
        logger.exception("Todo reminder email failed todo_id=%s", occurrence.id)
        return None
    if result.outcome is EmailOutcome.REJECTED:
        logger.warning("Todo reminder email refused; not retried todo_id=%s", occurrence.id)
    return result


async def _mark(session: AsyncSession, occurrence: TodoEmailSnapshot, now: datetime) -> None:
    try:
        await mark_reminder_emailed(session, occurrence, sent_at=now)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Todo reminder email mark failed todo_id=%s", occurrence.id)


async def run_email_reminder_cycle(
    session: AsyncSession,
    settings: Settings,
    *,
    keep_lock: Callable[[], Awaitable[bool]] | None = None,
    redis: Redis | None = None,
) -> int:
    if not settings.email_enabled or not settings.email_reminders_scheduler_enabled:
        return 0
    now = datetime.now(UTC)
    backoff = SendBackoff.for_channel(redis, settings, "email") if redis is not None else None
    return await process_todo_reminder_emails(
        session, settings, now=now, keep_lock=keep_lock, backoff=backoff
    )
