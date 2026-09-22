"""HTTP surface for the dedicated My Job product."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.core.jobs import enqueue
from app.models.orm import User
from app.models.schemas.job_search import (
    CoverLetterOut,
    JobMatchStatusUpdate,
    JobSearchDashboardOut,
    JobSearchRunOut,
    JobSearchStateUpdate,
    JobSearchUpsert,
)
from app.services import job_search as job_search_service

router = APIRouter(prefix="/job-search", tags=["job-search"])
_SEPARATE_BOOKMARKS_VERSION = "separate-v1"


def _uses_separate_bookmarks(bookmark_model: str | None) -> bool:
    return bookmark_model == _SEPARATE_BOOKMARKS_VERSION


def _map_error(exc: job_search_service.JobSearchError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=JobSearchDashboardOut)
async def get_job_search(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    bookmark_model: str | None = Header(default=None, alias="X-Recall-Job-Bookmarks"),
) -> JobSearchDashboardOut:
    return await job_search_service.get_dashboard(
        session,
        user,
        settings,
        separate_bookmarks=_uses_separate_bookmarks(bookmark_model),
    )


@router.put("", response_model=JobSearchDashboardOut)
async def upsert_job_search(
    body: JobSearchUpsert,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    bookmark_model: str | None = Header(default=None, alias="X-Recall-Job-Bookmarks"),
) -> JobSearchDashboardOut:
    try:
        return await job_search_service.upsert_profile(
            session,
            user,
            settings,
            body,
            separate_bookmarks=_uses_separate_bookmarks(bookmark_model),
        )
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.post("/run", response_model=JobSearchRunOut, status_code=status.HTTP_202_ACCEPTED)
async def run_job_search_now(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> JobSearchRunOut:
    """Queue a retry or first run from the dedicated My Job UI.

    Pro users may run on demand. Free users can retry a failed run so a
    transient provider outage never costs them an entire weekly delivery.
    """
    profile = await job_search_service.get_profile_for_user(session, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Job search not found")
    if profile.status != "active":
        raise HTTPException(
            status_code=409,
            detail="Resume My Job before starting a search",
        )
    if not job_search_service.can_request_manual_run(user, profile):
        raise HTTPException(status_code=403, detail="On-demand searches require Recall Pro")
    await enqueue(
        redis,
        "job_search_run",
        {"profile_id": str(profile.id), "manual": True},
        dedupe_key=f"job_search_retry:{profile.id}:{profile.last_run_at or 'never'}",
    )
    return JobSearchRunOut()


@router.patch("/status", response_model=JobSearchDashboardOut)
async def update_job_search_status(
    body: JobSearchStateUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    bookmark_model: str | None = Header(default=None, alias="X-Recall-Job-Bookmarks"),
) -> JobSearchDashboardOut:
    try:
        return await job_search_service.set_search_status(
            session,
            user,
            settings,
            body.status,
            separate_bookmarks=_uses_separate_bookmarks(bookmark_model),
        )
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.patch("/matches/{match_id}", response_model=JobSearchDashboardOut)
async def update_job_match_status(
    match_id: UUID,
    body: JobMatchStatusUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    bookmark_model: str | None = Header(default=None, alias="X-Recall-Job-Bookmarks"),
) -> JobSearchDashboardOut:
    try:
        return await job_search_service.set_match_status(
            session,
            user,
            settings,
            match_id,
            body.status,
            body.notes,
            is_saved=body.is_saved,
            separate_bookmarks=_uses_separate_bookmarks(bookmark_model),
        )
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.post("/matches/{match_id}/cover-letter", response_model=CoverLetterOut)
async def generate_job_cover_letter(
    match_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> CoverLetterOut:
    try:
        return await job_search_service.generate_cover_letter(
            session,
            user,
            settings,
            redis,
            match_id,
        )
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_search(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    await job_search_service.delete_profile(session, user, settings)
