"""Periodic cleanup of attachment rows never linked to a chat message."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.services import attachment_lifecycle

logger = logging.getLogger(__name__)

LOCK_KEY = "recall:attachment_orphan_reaper:lock"

_task: asyncio.Task | None = None


async def run_orphan_reaper_cycle(settings: Settings) -> None:
    interval = settings.attachment_orphan_reaper_interval_seconds
    redis = get_redis_client()
    acquired = await redis.set(LOCK_KEY, "1", nx=True, ex=max(interval - 30, 60))
    if not acquired:
        return
    try:
        await attachment_lifecycle.reap_orphan_attachments(settings)
    except Exception:
        logger.exception("Attachment orphan reaper cycle failed")
    finally:
        await redis.delete(LOCK_KEY)


async def orphan_reaper_loop(settings: Settings) -> None:
    interval = settings.attachment_orphan_reaper_interval_seconds
    while True:
        try:
            await run_orphan_reaper_cycle(settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Attachment orphan reaper loop error")
        await asyncio.sleep(interval)


async def start_orphan_reaper(settings: Settings) -> None:
    global _task
    if _task is not None:
        return
    _task = asyncio.create_task(orphan_reaper_loop(settings))


async def stop_orphan_reaper() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
