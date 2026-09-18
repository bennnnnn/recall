import logging

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.core.jobs import enqueue
from app.models.orm import User
from app.models.schemas.job_search import (
    JobMatchStatusUpdate,
    JobSearchDashboardOut,
    JobSearchStateUpdate,
    JobSearchUpsert,
)
from app.services import job_search as job_search_service
from app.services import job_search_run_now as job_search_run_now_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/job-search", tags=["job-search"])


def _map_error(exc: job_search_service.JobSearchError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=JobSearchDashboardOut)
async def get_job_search(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> JobSearchDashboardOut:
    try:
        return await job_search_service.get_dashboard(session, user, settings)
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.put("", response_model=JobSearchDashboardOut)
async def upsert_job_search(
    body: JobSearchUpsert,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> JobSearchDashboardOut:
    try:
        return await job_search_service.upsert_profile(session, user, settings, body)
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.patch("/status", response_model=JobSearchDashboardOut)
async def update_job_search_status(
    body: JobSearchStateUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> JobSearchDashboardOut:
    try:
        return await job_search_service.set_search_status(session, user, settings, body.status)
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.patch("/matches/{match_id}", response_model=JobSearchDashboardOut)
async def update_job_match_status(
    match_id: str,
    body: JobMatchStatusUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> JobSearchDashboardOut:
    try:
        return await job_search_service.set_match_status(
            session,
            user,
            settings,
            match_id,
            body.status,
        )
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.post("/run-now", response_model=JobSearchDashboardOut)
async def run_job_search_now(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> JobSearchDashboardOut:
    try:
        dashboard = await job_search_run_now_service.prepare_manual_run(
            session,
            user,
            settings,
        )
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc

    profile = dashboard.profile
    if profile is not None:
        # A manual run is an extra occurrence, not a reschedule. Key the queue
        # claim to the previous completed occurrence so repeated taps before
        # the worker starts collapse into one job while a later run remains
        # possible after the ten-minute guard expires.
        previous_run = profile.last_run_at.isoformat() if profile.last_run_at else "never"
        try:
            await enqueue(
                redis,
                "automation_run",
                {"automation_id": str(profile.id)},
                dedupe_key=f"automation_run_manual:{profile.id}:{previous_run}",
            )
        except Exception:
            logger.exception("Immediate My Job enqueue failed profile_id=%s", profile.id)
    return dashboard


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_search(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    try:
        await job_search_service.delete_profile(session, user, settings)
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc
