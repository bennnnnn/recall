"""Periodic email reminder scheduler — todo due + learning nudges (opt-in)."""

from __future__ import annotations

import logging

from app.background.periodic import (
    CycleLock,
    lock_ttl_hold_across_ticks,
    run_locked_cycle,
    start_periodic,
    stop_periodic,
)
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.services import reminder_emails

logger = logging.getLogger(__name__)

_NAME = "email_reminders"
LOCK_KEY = "recall:email_reminders:lock"
INTERVAL_SECONDS = 60
LOCK_TTL_SECONDS = lock_ttl_hold_across_ticks(INTERVAL_SECONDS)


def _email_reminders_enabled(settings: Settings) -> bool:
    return settings.email_enabled and settings.email_reminders_scheduler_enabled


async def _email_cycle(settings: Settings, _lock: CycleLock) -> None:
    redis = get_redis_client()
    async with SessionLocal() as session:
        count = await reminder_emails.run_email_reminder_cycle(session, redis, settings)
        if count:
            logger.info("Email reminder cycle sent count=%s", count)


async def run_email_reminder_cycle(settings: Settings) -> None:
    await run_locked_cycle(
        name="email reminders",
        lock_key=LOCK_KEY,
        lock_ttl_seconds=LOCK_TTL_SECONDS,
        enabled=_email_reminders_enabled(settings),
        fn=_email_cycle,
        settings=settings,
    )


async def start_email_reminder_scheduler(settings: Settings) -> None:
    await start_periodic(
        name=_NAME,
        interval_seconds=INTERVAL_SECONDS,
        enabled=_email_reminders_enabled(settings),
        cycle=run_email_reminder_cycle,
        settings=settings,
    )


async def stop_email_reminder_scheduler() -> None:
    await stop_periodic(_NAME)
