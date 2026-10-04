"""HTTP surface for the dedicated My Job product."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.models.orm import User
from app.modules.job_search import service as job_search_service
from app.modules.job_search.runs import owned_run, submit_run
from app.modules.job_search.schemas import (
    CoverLetterOut,
    JobMatchOut,
    JobMatchPageOut,
    JobMatchStatusUpdate,
    JobRunStatusOut,
    JobSearchDashboardOut,
    JobSearchPreferencesPatch,
    JobSearchRunOut,
    JobSearchStateUpdate,
    JobSearchUpsert,
)

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
    include_matches: bool = True,
) -> JobSearchDashboardOut:
    return await job_search_service.get_dashboard(
        session,
        user,
        settings,
        separate_bookmarks=_uses_separate_bookmarks(bookmark_model),
        include_matches=include_matches,
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


@router.patch("", response_model=JobSearchDashboardOut)
async def patch_job_search(
    body: JobSearchPreferencesPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> JobSearchDashboardOut:
    try:
        return await job_search_service.patch_profile(session, user, settings, body)
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.post("/run", response_model=JobSearchRunOut, status_code=status.HTTP_202_ACCEPTED)
async def run_job_search_now(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
    request_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=160),
) -> JobSearchRunOut:
    try:
        run = await submit_run(session, user, settings, redis, request_key=request_key)
        return JobSearchRunOut(
            run_id=run.id, state=run.state, queued=run.state in {"queued", "running"}
        )
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.get("/runs/{run_id}", response_model=JobRunStatusOut)
async def get_run(
    run_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> JobRunStatusOut:
    try:
        return JobRunStatusOut.model_validate(await owned_run(session, user.id, run_id))
    except job_search_service.JobSearchError as exc:
        raise _map_error(exc) from exc


@router.get("/matches", response_model=JobMatchPageOut)
async def list_matches(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    offset: int = 0,
    limit: int = 30,
    kind: str | None = None,
    run_id: UUID | None = None,
    view: str = "all",
) -> JobMatchPageOut:
    from sqlalchemy import func, select

    from app.modules.job_search.models import JobMatch, JobSearchProfile, JobSearchRun
    from app.modules.job_search.ranking import _profile_from_rows

    if (
        offset < 0
        or not 1 <= limit <= 100
        or kind not in {None, "qualifying", "possible"}
        or view not in {"new", "all", "applied"}
    ):
        raise HTTPException(status_code=422, detail="Invalid page")
    run = None
    if run_id:
        try:
            run = await owned_run(session, user.id, run_id)
        except job_search_service.JobSearchError as exc:
            raise _map_error(exc) from exc
    profile = await job_search_service.get_profile_for_user(session, user.id)
    if profile is None:
        return JobMatchPageOut(matches=[])
    query = (
        select(JobMatch)
        .join(JobSearchProfile)
        .where(JobSearchProfile.user_id == user.id, JobMatch.status != "hidden")
    )
    if kind:
        query = query.where(JobMatch.match_kind == kind)
    if not run_id and view == "new":
        run = await session.scalar(
            select(JobSearchRun)
            .where(JobSearchRun.profile_id == profile.id, JobSearchRun.state == "completed")
            .order_by(JobSearchRun.finished_at.desc(), JobSearchRun.id.desc())
            .limit(1)
        )
    if run is not None:
        query = query.where(JobMatch.id.in_([UUID(value) for value in run.match_ids]))
    if view == "new":
        if run is not None:
            # Publishing uses one timestamp for new rows and the completed run.
            # A rediscovered opening keeps its original found_at and stays in All.
            query = query.where(JobMatch.found_at == run.finished_at)
        else:
            # Retain the latest legacy batch when no durable successful run exists.
            latest_found = select(func.max(JobMatch.found_at)).where(
                JobMatch.profile_id == profile.id
            )
            query = query.where(JobMatch.found_at == latest_found.scalar_subquery())
    elif view == "applied":
        query = query.where(JobMatch.status == "applied")
    rows = list(
        (
            await session.scalars(
                query.order_by(
                    func.coalesce(JobMatch.checked_at, JobMatch.found_at).desc(),
                    JobMatch.id.desc(),
                )
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
    )
    snapshot = _profile_from_rows(profile, user)
    return JobMatchPageOut(
        matches=[
            job_search_service.match_out(row, profile_snapshot=snapshot) for row in rows[:limit]
        ],
        next_offset=offset + limit if len(rows) > limit else None,
    )


@router.get("/matches/{match_id}", response_model=JobMatchOut)
async def get_match(
    match_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> JobMatchOut:
    from sqlalchemy import select

    from app.modules.job_search.models import JobMatch, JobSearchProfile
    from app.modules.job_search.ranking import _profile_from_rows

    match = await session.scalar(
        select(JobMatch)
        .join(JobSearchProfile)
        .where(JobMatch.id == match_id, JobSearchProfile.user_id == user.id)
    )
    profile = await job_search_service.get_profile_for_user(session, user.id)
    if match is None or profile is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_search_service.match_out(match, profile_snapshot=_profile_from_rows(profile, user))


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
            notes_provided="notes" in body.model_fields_set,
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
