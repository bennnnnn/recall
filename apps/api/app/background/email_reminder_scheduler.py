"""Periodic email reminder scheduler — todo due + learning nudges (opt-in)."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.core.redis_lock import acquire_lock, release_lock
from app.services import reminder_emails

logger = logging.getLogger(__name__)

LOCK_KEY = "recall:email_reminders:lock"
INTERVAL_SECONDS = 60
LOCK_TTL_SECONDS = max(INTERVAL_SECONDS * 10, 300)


async def run_email_reminder_cycle(settings: Settings) -> None:
    redis = get_redis_client()
    token = await acquire_lock(redis, LOCK_KEY, LOCK_TTL_SECONDS)
    if not token:
        return
    try:
        async with SessionLocal() as session:
            count = await reminder_emails.run_email_reminder_cycle(session, redis, settings)
            if count:
                logger.info("Email reminder cycle sent count=%s", count)
    except Exception:
        logger.exception("Email reminder cycle failed")
    finally:
        await release_lock(redis, LOCK_KEY, token)


async def email_reminder_loop(settings: Settings) -> None:
    while True:
        try:
            await run_email_reminder_cycle(settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Email reminder loop error")
        await asyncio.sleep(INTERVAL_SECONDS)


_email_task: asyncio.Task | None = None


async def start_email_reminder_scheduler(settings: Settings) -> None:
    global _email_task
    if _email_task is not None:
        return
    _email_task = asyncio.create_task(email_reminder_loop(settings))


async def stop_email_reminder_scheduler() -> None:
    global _email_task
    if _email_task is None:
        return
    _email_task.cancel()
    try:
        await _email_task
    except asyncio.CancelledError:
        pass
    _email_task = None
