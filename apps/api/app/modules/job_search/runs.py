"""Durable admission, allowance reservation and run recovery shared by chat/screens."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.jobs import enqueue
from app.models.orm import User
from app.modules.job_search.models import JobManualAllowance, JobSearchProfile, JobSearchRun
from app.modules.job_search.service import JobSearchError, preference_values, require_pro

logger = logging.getLogger(__name__)
MANUAL_LIMIT = 5
COOLDOWN = timedelta(minutes=10)
ACTIVE_STATES = ("queued", "running")
TERMINAL_STATES = ("completed", "failed", "limited", "cancelled")


def local_day(now: datetime, timezone: str | None) -> str:
    try:
        zone = ZoneInfo(timezone or "UTC")
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")
    return now.astimezone(zone).date().isoformat()


async def latest_run(session: AsyncSession, profile_id: UUID) -> JobSearchRun | None:
    return await session.scalar(
        select(JobSearchRun)
        .where(JobSearchRun.profile_id == profile_id)
        .order_by(JobSearchRun.created_at.desc())
        .limit(1)
    )


async def allowance(
    session: AsyncSession, profile: JobSearchProfile, user: User, *, now: datetime | None = None
) -> tuple[int, datetime | None]:
    now = now or datetime.now(UTC)
    used = await session.scalar(
        select(func.count())
        .select_from(JobSearchRun)
        .where(
            JobSearchRun.profile_id == profile.id,
            JobSearchRun.manual.is_(True),
            JobSearchRun.local_day == local_day(now, user.timezone),
        )
    )
    latest = await session.scalar(
        select(JobSearchRun)
        .where(JobSearchRun.profile_id == profile.id, JobSearchRun.manual.is_(True))
        .order_by(JobSearchRun.created_at.desc())
        .limit(1)
    )
    reserved = await session.get(JobManualAllowance, (user.id, local_day(now, user.timezone)))
    used = max(used or 0, reserved.reserved_count if reserved else 0)
    last_reserved = await session.scalar(
        select(func.max(JobManualAllowance.last_requested_at)).where(
            JobManualAllowance.user_id == user.id
        )
    )
    last_time = max(
        [
            value
            for value in (latest.created_at if latest else None, last_reserved)
            if value is not None
        ],
        default=None,
    )
    cooldown = last_time + COOLDOWN if last_time else None
    return max(0, MANUAL_LIMIT - (used or 0)), cooldown if cooldown and cooldown > now else None


async def dispatch(redis: Redis, run: JobSearchRun) -> None:
    # Persist first. A transport failure is recovered by the scheduler.
    try:
        await enqueue(
            redis,
            "job_search_run",
            {"run_id": str(run.id)},
            dedupe_key=f"job-run:{run.id}:{run.attempts}",
        )
    except Exception:
        logger.exception("My Job dispatch deferred run_id=%s", run.id)


async def submit_run(
    session: AsyncSession,
    user: User,
    settings: Settings,
    redis: Redis,
    *,
    request_key: str | None = None,
    manual: bool = True,
    overrides: dict[str, Any] | None = None,
    result_limit: int | None = None,
) -> JobSearchRun:
    require_pro(user)
    if not settings.job_search_premium_enabled:
        raise JobSearchError("My Job searches are not available yet", status_code=503)
    profile = await session.scalar(
        select(JobSearchProfile).where(JobSearchProfile.user_id == user.id).with_for_update()
    )
    if profile is None:
        raise JobSearchError("Set up My Job first", status_code=404)
    request_key = (request_key or str(uuid4()))[:160]
    existing = await session.scalar(
        select(JobSearchRun).where(
            JobSearchRun.profile_id == profile.id, JobSearchRun.request_key == request_key
        )
    )
    if existing:
        await session.commit()
        if existing.state == "queued":
            await dispatch(redis, existing)
        return existing
    if profile.needs_review:
        raise JobSearchError(
            "Review the country and salary currency in My Job before searching", status_code=422
        )
    if profile.status != "active":
        raise JobSearchError("Resume My Job before starting a search", status_code=409)
    active = await session.scalar(
        select(JobSearchRun)
        .where(JobSearchRun.profile_id == profile.id, JobSearchRun.state.in_(ACTIVE_STATES))
        .order_by(JobSearchRun.created_at.desc())
        .limit(1)
    )
    if active:
        await session.commit()
        return active
    if overrides:
        from pydantic import ValidationError

        from app.modules.job_search.schemas import JobSearchPreferencesPatch

        try:
            patch = JobSearchPreferencesPatch.model_validate(overrides)
            overrides = preference_values(profile, patch)
        except ValidationError as exc:
            raise JobSearchError("Check the temporary search preferences", status_code=422) from exc
    now = datetime.now(UTC)
    if manual:
        # A user lock keeps reservations consistent even across search recreation.
        await session.scalar(select(User).where(User.id == user.id).with_for_update())
        remaining, cooldown = await allowance(session, profile, user, now=now)
        if not remaining:
            raise JobSearchError(
                "Five manual searches used today. Scheduled delivery continues.", status_code=429
            )
        if cooldown:
            raise JobSearchError("Wait ten minutes between manual searches", status_code=429)
    if result_limit is not None and not 1 <= result_limit <= 15:
        raise JobSearchError("Choose between 1 and 15 results", status_code=422)
    run = JobSearchRun(
        profile_id=profile.id,
        request_key=request_key,
        profile_revision=profile.revision or 1,
        manual=manual,
        local_day=local_day(now, user.timezone),
        created_at=now,
        overrides=overrides or {},
        result_limit=result_limit,
    )
    session.add(run)
    if manual:
        reserved = await session.get(JobManualAllowance, (user.id, run.local_day))
        if reserved is None:
            reserved = JobManualAllowance(user_id=user.id, local_day=run.local_day)
            session.add(reserved)
        reserved.reserved_count = MANUAL_LIMIT - remaining + 1
        reserved.last_requested_at = now
    await session.commit()
    await session.refresh(run)
    await dispatch(redis, run)
    return run


async def owned_run(session: AsyncSession, user_id: UUID, run_id: UUID) -> JobSearchRun:
    run = await session.scalar(
        select(JobSearchRun)
        .join(JobSearchProfile)
        .where(JobSearchRun.id == run_id, JobSearchProfile.user_id == user_id)
    )
    if run is None:
        raise JobSearchError("Search not found", status_code=404)
    return run
