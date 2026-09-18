"""Periodic scheduler that enqueues due Automations for headless execution.

Mirrors `push_scheduler.py` / `gmail_periodic_sync.py`'s lock pattern. This
loop only reads due rows and enqueues a durable job per row — it never
mutates an automation's schedule. `services/automations/run.py` (the
`automation_run` job handler) owns every schedule mutation, so a run that
never gets picked up (crash, dedupe collision) simply leaves the row due
for the next tick instead of silently losing the occurrence.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.background.periodic import (
    CycleLock,
    lock_ttl_hold_across_ticks,
    run_locked_cycle,
    start_periodic,
    stop_periodic,
)
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.jobs import enqueue
from app.core.redis import get_redis_client
from app.repositories import automations as automations_repo

logger = logging.getLogger(__name__)

_NAME = "automations"
LOCK_KEY = "recall:automations:lock"
INTERVAL_SECONDS = 60
# Bounded work per tick (a DB read + N enqueues) — hold the lock across
# ticks rather than yielding, same as push_scheduler.
LOCK_TTL_SECONDS = lock_ttl_hold_across_ticks(INTERVAL_SECONDS)


async def _automations_cycle(settings: Settings, _lock: CycleLock) -> None:
    redis = get_redis_client()
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        due = await automations_repo.list_due(session, cutoff=now, limit=100)
    if not due:
        return
    for automation in due:
        # dedupe_key includes the still-unadvanced next_run_at, so a second
        # tick before the job handler advances the schedule (slow run, or a
        # crash) cannot double-enqueue the same occurrence.
        await enqueue(
            redis,
            "automation_run",
            {"automation_id": str(automation.id)},
            dedupe_key=f"automation_run:{automation.id}:{automation.next_run_at.isoformat()}",
        )
    logger.info("Automations cycle enqueued count=%s", len(due))


async def run_automations_cycle(settings: Settings) -> None:
    await run_locked_cycle(
        name="automations",
        lock_key=LOCK_KEY,
        lock_ttl_seconds=LOCK_TTL_SECONDS,
        enabled=settings.automations_enabled,
        fn=_automations_cycle,
        settings=settings,
    )


async def start_automations_scheduler(settings: Settings) -> None:
    await start_periodic(
        name=_NAME,
        interval_seconds=INTERVAL_SECONDS,
        enabled=settings.automations_enabled,
        cycle=run_automations_cycle,
        settings=settings,
    )


async def stop_automations_scheduler() -> None:
    await stop_periodic(_NAME)
