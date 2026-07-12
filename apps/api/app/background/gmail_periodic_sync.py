"""Periodic Gmail sync for all connected users (hourly throttle per user)."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.core.redis_lock import acquire_lock, release_lock
from app.repositories import gmail_connections as gmail_repo
from app.services import email as email_service

logger = logging.getLogger(__name__)

LOCK_KEY = "recall:gmail_periodic:lock"
CHECK_INTERVAL_SECONDS = 900  # scan every 15 min; sync users stale > gmail_sync_interval


async def run_gmail_periodic_cycle(settings: Settings) -> None:
    if not settings.gmail_enabled:
        return
    redis = get_redis_client()
    token = await acquire_lock(redis, LOCK_KEY, CHECK_INTERVAL_SECONDS - 30)
    if not token:
        return
    try:
        async with SessionLocal() as session:
            connections = await gmail_repo.list_all(session)
        due = [
            conn
            for conn in connections
            if email_service.gmail_sync_is_due(conn.last_sync_at, settings)
        ]

        semaphore = asyncio.Semaphore(max(1, settings.gmail_periodic_sync_concurrency))

        async def _sync_one(user_id: UUID) -> None:
            async with semaphore:
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

        await asyncio.gather(*(_sync_one(conn.user_id) for conn in due))
    except Exception:
        logger.exception("Gmail periodic cycle failed")
    finally:
        await release_lock(redis, LOCK_KEY, token)


async def gmail_periodic_loop(settings: Settings) -> None:
    while True:
        try:
            await run_gmail_periodic_cycle(settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Gmail periodic loop error")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


_task: asyncio.Task | None = None


async def start_gmail_periodic_scheduler(settings: Settings) -> None:
    global _task
    if _task is not None or not settings.gmail_enabled:
        return
    _task = asyncio.create_task(gmail_periodic_loop(settings))


async def stop_gmail_periodic_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
