"""Periodic push notification scheduler — reminders, learning nudges, email suggestions."""

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
from app.services import push_notifications

logger = logging.getLogger(__name__)

_NAME = "push"
LOCK_KEY = "recall:push:lock"
INTERVAL_SECONDS = 60
LOCK_TTL_SECONDS = lock_ttl_hold_across_ticks(INTERVAL_SECONDS)


async def _push_cycle(settings: Settings, _lock: CycleLock) -> None:
    redis = get_redis_client()
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


async def run_push_cycle(settings: Settings) -> None:
    await run_locked_cycle(
        name="push",
        lock_key=LOCK_KEY,
        lock_ttl_seconds=LOCK_TTL_SECONDS,
        enabled=settings.push_enabled,
        fn=_push_cycle,
        settings=settings,
    )


async def start_push_scheduler(settings: Settings) -> None:
    await start_periodic(
        name=_NAME,
        interval_seconds=INTERVAL_SECONDS,
        enabled=settings.push_enabled,
        cycle=run_push_cycle,
        settings=settings,
    )


async def stop_push_scheduler() -> None:
    await stop_periodic(_NAME)
