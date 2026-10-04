"""Periodic enqueue loop for due My Job profiles."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.background.periodic import start_periodic, stop_periodic
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.jobs import enqueue
from app.core.redis import get_redis_client
from app.models.orm import User
from app.modules.billing import is_pro
from app.modules.job_search.models import JobNotificationEvent, JobSearchProfile, JobSearchRun
from app.modules.job_search.runs import dispatch, submit_run
from app.modules.job_search.service import JobSearchError

_NAME = "job-search"
_INTERVAL_SECONDS = 60
_BATCH_SIZE = 100


async def _cycle(settings: Settings) -> None:
    from sqlalchemy import or_

    now = datetime.now(UTC)
    redis = get_redis_client()
    async with SessionLocal() as session:
        # Recovery is independent of provider availability and queue restarts.
        pending = list(
            (
                await session.scalars(
                    select(JobSearchRun)
                    .where(
                        or_(
                            JobSearchRun.state == "queued",
                            (JobSearchRun.state == "running") & (JobSearchRun.lease_until <= now),
                        )
                    )
                    .limit(_BATCH_SIZE)
                )
            ).all()
        )
        for run in pending:
            await dispatch(redis, run)
        events = list(
            (
                await session.scalars(
                    select(JobNotificationEvent)
                    .where(
                        JobNotificationEvent.state == "pending",
                        JobNotificationEvent.next_attempt_at <= now,
                        or_(
                            JobNotificationEvent.lease_until.is_(None),
                            JobNotificationEvent.lease_until <= now,
                        ),
                    )
                    .limit(_BATCH_SIZE)
                )
            ).all()
        )
        for event in events:
            await enqueue(
                redis,
                "job_notification",
                {"event_id": str(event.id)},
                dedupe_key=f"job-notification:{event.id}:{event.attempts}",
            )
        due = (
            await session.execute(
                select(JobSearchProfile, User)
                .join(User, User.id == JobSearchProfile.user_id)
                .where(JobSearchProfile.status == "active", JobSearchProfile.next_run_at <= now)
                .order_by(JobSearchProfile.next_run_at)
                .limit(_BATCH_SIZE)
            )
        ).all()
        for profile, user in due:
            if user is None or not is_pro(user):
                profile.status, profile.suspension_reason = "paused", "pro_expired"
                profile.revision = (profile.revision or 1) + 1
                await session.commit()
                continue
            if not settings.web_search_enabled or not settings.job_search_premium_enabled:
                continue
            try:
                await submit_run(
                    session,
                    user,
                    settings,
                    redis,
                    manual=False,
                    request_key=f"scheduled:{profile.next_run_at.isoformat()}",
                )
            except JobSearchError:
                # A concurrent pause or edit is ordinary; try next cycle.
                await session.rollback()


async def start_job_search_scheduler(settings: Settings) -> None:
    await start_periodic(
        name=_NAME,
        interval_seconds=_INTERVAL_SECONDS,
        enabled=True,
        cycle=_cycle,
        settings=settings,
    )


async def stop_job_search_scheduler() -> None:
    await stop_periodic(_NAME)
