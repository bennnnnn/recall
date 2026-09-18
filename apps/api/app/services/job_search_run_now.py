"""Prepare a My Job manual run without moving its recurring schedule."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import User
from app.models.schemas.job_search import JobSearchDashboardOut
from app.repositories import automations as automations_repo
from app.services import job_search as job_search_service
from app.services import plan as plan_service


async def prepare_manual_run(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> JobSearchDashboardOut:
    """Validate and activate an immediate search while keeping its next cadence.

    A manual run is an extra occurrence, not a reschedule. The worker receives
    a direct queue entry from the router and advances nothing when the stored
    ``next_run_at`` is still in the future.
    """
    if not settings.automations_enabled:
        raise job_search_service.JobSearchError("My Job is not available", status_code=404)
    if not plan_service.is_pro(user):
        raise job_search_service.JobSearchError(
            "Run now requires Recall Pro",
            status_code=403,
        )

    automation = await automations_repo.get_job_search_for_user(session, user.id)
    if automation is None:
        raise job_search_service.JobSearchError(
            "Set up your job search first",
            status_code=404,
        )

    now = datetime.now(UTC)
    if automation.last_run_at is not None and now - automation.last_run_at < timedelta(
        minutes=10
    ):
        raise job_search_service.JobSearchError(
            "A job search ran recently. Try again in a few minutes.",
            status_code=429,
        )

    if automation.status != "active":
        await automations_repo.update(session, automation, status="active")

    return await job_search_service.get_dashboard(session, user, settings)
