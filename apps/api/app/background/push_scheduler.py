"""Periodic push notification scheduler — reminders, learning nudges, email suggestions."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.core.redis_lock import acquire_lock, release_lock
from app.services import push_notifications

logger = logging.getLogger(__name__)

LOCK_KEY = "recall:push:lock"
INTERVAL_SECONDS = 60
# Hold the lock longer than one loop tick and typical cycle runtime so a slow
# run cannot overlap with a second instance/replica.
LOCK_TTL_SECONDS = max(INTERVAL_SECONDS * 10, 300)


async def run_push_cycle(settings: Settings) -> None:
    redis = get_redis_client()
    token = await acquire_lock(redis, LOCK_KEY, LOCK_TTL_SECONDS)
    if not token:
        return
    try:
        async with SessionLocal() as session:
            count = await push_notifications.run_push_cycle(session, redis, settings)
            if count:
                logger.info("Push cycle sent count=%s", count)
    except Exception:
        logger.exception("Push cycle failed")
    finally:
        await release_lock(redis, LOCK_KEY, token)


async def push_loop(settings: Settings) -> None:
    while True:
        try:
            await run_push_cycle(settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Push loop error")
        await asyncio.sleep(INTERVAL_SECONDS)


_push_task: asyncio.Task | None = None


async def start_push_scheduler(settings: Settings) -> None:
    global _push_task
    if _push_task is not None:
        return
    _push_task = asyncio.create_task(push_loop(settings))


async def stop_push_scheduler() -> None:
    global _push_task
    if _push_task is None:
        return
    _push_task.cancel()
    try:
        await _push_task
    except asyncio.CancelledError:
        pass
    _push_task = None
