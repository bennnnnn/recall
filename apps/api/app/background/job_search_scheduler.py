"""Periodic enqueue loop for due My Job profiles."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.background.periodic import start_periodic, stop_periodic
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.jobs import enqueue
from app.core.redis import get_redis_client
from app.models.orm import JobSearchProfile

_NAME = "job-search"
_INTERVAL_SECONDS = 60
_BATCH_SIZE = 100


async def _cycle(settings: Settings) -> None:
    if not settings.web_search_enabled:
        return
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        due = list(
            (
                await session.scalars(
                    select(JobSearchProfile)
                    .where(
                        JobSearchProfile.status == "active",
                        JobSearchProfile.next_run_at <= now,
                    )
                    .order_by(JobSearchProfile.next_run_at.asc())
                    .limit(_BATCH_SIZE)
                )
            ).all()
        )

    redis = get_redis_client()
    for profile in due:
        await enqueue(
            redis,
            "job_search_run",
            {"profile_id": str(profile.id), "manual": False},
            dedupe_key=f"job_search_run:{profile.id}:{profile.next_run_at.isoformat()}",
        )


async def start_job_search_scheduler(settings: Settings) -> None:
    await start_periodic(
        name=_NAME,
        interval_seconds=_INTERVAL_SECONDS,
        enabled=settings.web_search_enabled,
        cycle=_cycle,
        settings=settings,
    )


async def stop_job_search_scheduler() -> None:
    await stop_periodic(_NAME)
