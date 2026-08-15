"""Periodic Gmail sync for all connected users (hourly throttle per user)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.background.periodic import (
    CycleLock,
    lock_ttl_yield_next_tick,
    run_locked_cycle,
    start_periodic,
    stop_periodic,
)
from app.core.config import Settings
from app.core.db import SessionLocal
from app.repositories import gmail_connections as gmail_repo
from app.services import email as email_service

logger = logging.getLogger(__name__)

_NAME = "gmail_periodic"
LOCK_KEY = "recall:gmail_periodic:lock"
CHECK_INTERVAL_SECONDS = 900  # scan every 15 min; sync users stale > gmail_sync_interval
LOCK_TTL_SECONDS = lock_ttl_yield_next_tick(CHECK_INTERVAL_SECONDS)


async def _gmail_cycle(settings: Settings, lock: CycleLock) -> None:
    redis = lock.redis
    async with SessionLocal() as session:
        cutoff = datetime.now(UTC) - timedelta(seconds=settings.gmail_sync_interval_seconds)
        due = await gmail_repo.list_due(
            session,
            cutoff=cutoff,
            limit=max(1, settings.gmail_periodic_sync_batch_size),
        )

    semaphore = asyncio.Semaphore(max(1, settings.gmail_periodic_sync_concurrency))
    abort = asyncio.Event()

    async def _sync_one(user_id: UUID) -> None:
        if abort.is_set():
            return
        async with semaphore:
            if abort.is_set():
                return
            try:
                async with SessionLocal() as session:
                    await email_service.sync_gmail_for_user(
                        session,
                        settings,
                        user_id,
                        redis=redis,
                    )
            except Exception:
                logger.exception("Periodic Gmail sync failed user_id=%s", user_id)
            if not await lock.refresh():
                abort.set()
                logger.warning("Gmail periodic lock lost; skipping remaining users")

    await asyncio.gather(*(_sync_one(conn.user_id) for conn in due))


async def run_gmail_periodic_cycle(settings: Settings) -> None:
    await run_locked_cycle(
        name="gmail periodic",
        lock_key=LOCK_KEY,
        lock_ttl_seconds=LOCK_TTL_SECONDS,
        enabled=settings.gmail_enabled,
        fn=_gmail_cycle,
        settings=settings,
    )


async def start_gmail_periodic_scheduler(settings: Settings) -> None:
    await start_periodic(
        name=_NAME,
        interval_seconds=CHECK_INTERVAL_SECONDS,
        enabled=settings.gmail_enabled,
        cycle=run_gmail_periodic_cycle,
        settings=settings,
    )


async def stop_gmail_periodic_scheduler() -> None:
    await stop_periodic(_NAME)
