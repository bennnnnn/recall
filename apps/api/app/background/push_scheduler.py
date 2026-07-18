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
        # Collect outbound under a short-lived DB session, then release before
        # Expo HTTP so Neon pool connections aren't held across network I/O.
        async with SessionLocal() as session:
            outbound = await push_notifications.collect_push_outbound(session, redis, settings)
            if not outbound:
                return

        delivered, invalid_tokens, receipt_tickets = await push_notifications.dispatch_expo(
            outbound, settings
        )

        async with SessionLocal() as session:
            if invalid_tokens:
                for expo_token in invalid_tokens:
                    try:
                        from app.repositories import push_tokens as push_repo

                        await push_repo.delete_by_token(session, expo_token)
                        logger.info("Pruned invalid push token=%s", expo_token[:20])
                    except Exception:
                        logger.debug("Failed to prune push token", exc_info=True)
            if receipt_tickets:
                await push_notifications.enqueue_push_receipts(redis, receipt_tickets)
            await push_notifications.finalize_push_deliveries(session, redis, outbound, delivered)
            count = len(outbound)
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
