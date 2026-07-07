from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import User
from app.models.schemas import (
    ProjectCreate,
    ProjectDailyHistoryDay,
    ProjectDetailOut,
    ProjectItemOut,
    ProjectItemUpdate,
    ProjectOut,
    ProjectStats,
    ProjectUpdate,
)
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services import daily_learning
from app.services import home as home_service
from app.services import projects as projects_service
from app.services import time_context as time_context_service

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_timezone(user: User, client_timezone: str | None) -> str:
    return time_context_service.effective_timezone(user.timezone, client_timezone)


def _daily_history_for_project(
    project,
    items: list,
    *,
    timezone_name: str,
) -> list[ProjectDailyHistoryDay]:
    raw = daily_learning.build_daily_history(
        items,
        timezone_name=timezone_name,
        daily_goal=daily_learning.resolve_daily_goal(project),
        active_since=project.created_at,
        days=14,
    )
    return [ProjectDailyHistoryDay.model_validate(row) for row in raw]


def _daily_items_by_date_for_project(
    items: list,
    *,
    timezone_name: str,
) -> dict[str, list[ProjectItemOut]]:
    grouped = daily_learning.group_mastered_items_by_date(
        items,
        timezone_name=timezone_name,
        days=14,
    )
    return {
        day_key: [ProjectItemOut.model_validate(item) for item in day_items]
        for day_key, day_items in grouped.items()
    }


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ProjectOut]:
    items = await projects_repo.list_for_user(session, user.id)
    return [ProjectOut.model_validate(item) for item in items if item.kind != "programming"]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    kind = body.kind
    if kind == "vocabulary":
        kind = "language"
    if kind == "programming":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="programming_not_supported",
        )
    if kind == "language":
        existing = await projects_repo.find_language_by_target(
            session, user.id, body.target_language
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="language_project_exists",
            )
    if kind == "trivia":
        existing = await projects_repo.find_trivia_project(session, user.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="trivia_project_exists",
            )
    item = await projects_repo.create(
        session,
        user_id=user.id,
        title=body.title,
        description=body.description,
        kind=kind,
        target_language=body.target_language,
        native_language=body.native_language,
        level=body.level,
        daily_goal=body.daily_goal if kind in ("language", "trivia") else None,
    )
    await home_service.invalidate_home_cache(user.id)
    return ProjectOut.model_validate(item)


@router.get("/{project_id}", response_model=ProjectDetailOut)
async def get_project(
    project_id: UUID,
    client_timezone: str | None = Query(default=None, max_length=64),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectDetailOut:
    item = await projects_repo.get_by_id(session, project_id, user.id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if item.kind == "programming":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    tz_name = _project_timezone(user, client_timezone)
    is_language = item.kind in ("language", "vocabulary")
    if is_language:
        await project_items_repo.normalize_pos_list_titles(session, user.id, project_id)
        project_items = await project_items_repo.list_for_user(
            session, user.id, project_id=project_id, limit=5000
        )
        stats = ProjectStats.model_validate(
            project_items_repo.stats_from_items(project_items, timezone_name=tz_name)
        )
        daily_history = _daily_history_for_project(item, project_items, timezone_name=tz_name)
        daily_items_by_date = _daily_items_by_date_for_project(project_items, timezone_name=tz_name)
        return ProjectDetailOut(
            **ProjectOut.model_validate(item).model_dump(),
            mastered_count=stats.mastered_count,
            total_count=stats.total,
            stats=stats,
            daily_history=daily_history,
            daily_items_by_date=daily_items_by_date,
            lists=[],
            by_part_of_speech=[],
            pos_groups=[],
        )

    if item.kind == "trivia":
        project_items = await project_items_repo.list_for_user(
            session, user.id, project_id=project_id, limit=5000
        )
        stats = ProjectStats.model_validate(
            project_items_repo.stats_from_items(project_items, timezone_name=tz_name)
        )
        daily_history = _daily_history_for_project(item, project_items, timezone_name=tz_name)
        daily_items_by_date = _daily_items_by_date_for_project(project_items, timezone_name=tz_name)
        lists = projects_service.group_trivia_items(project_items)
        return ProjectDetailOut(
            **ProjectOut.model_validate(item).model_dump(),
            mastered_count=stats.mastered_count,
            total_count=stats.total,
            stats=stats,
            daily_history=daily_history,
            daily_items_by_date=daily_items_by_date,
            lists=lists,
            by_part_of_speech=[],
            pos_groups=[],
        )

    project_items = await project_items_repo.list_for_user(session, user.id, project_id=project_id)
    stats = projects_service.build_stats(project_items)
    lists = projects_service.group_items(project_items)
    return ProjectDetailOut(
        **ProjectOut.model_validate(item).model_dump(),
        mastered_count=stats.mastered_count,
        total_count=stats.total,
        stats=stats,
        lists=lists,
        by_part_of_speech=projects_service.group_by_part_of_speech(project_items),
        pos_groups=[],
    )


@router.get("/{project_id}/daily-items", response_model=list[ProjectItemOut])
async def list_daily_items(
    project_id: UUID,
    activity_date: str = Query(..., min_length=10, max_length=10),
    client_timezone: str | None = Query(default=None, max_length=64),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectItemOut]:
    project = await projects_repo.get_by_id(session, project_id, user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.kind not in ("language", "vocabulary", "trivia"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Daily items are only available for language and trivia projects",
        )
    try:
        parsed_date = date.fromisoformat(activity_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="activity_date must be YYYY-MM-DD",
        ) from exc
    tz_name = _project_timezone(user, client_timezone)
    items = await project_items_repo.list_by_activity_date(
        session,
        user.id,
        project_id,
        parsed_date,
        timezone_name=tz_name,
        limit=limit,
        offset=offset,
    )
    return [ProjectItemOut.model_validate(i) for i in items]


@router.patch("/{project_id}/items/{item_id}", response_model=ProjectItemOut)
async def update_project_item(
    project_id: UUID,
    item_id: UUID,
    body: ProjectItemUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectItemOut:
    project = await projects_repo.get_by_id(session, project_id, user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    item = await project_items_repo.get_by_id(session, item_id, user.id, project_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    updated = await project_items_repo.update(session, item, **patch)
    await home_service.invalidate_home_cache(user.id)
    return ProjectItemOut.model_validate(updated)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    item = await projects_repo.get_by_id(session, project_id, user.id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    patch = body.model_dump(exclude_unset=True)
    if patch.get("kind") == "programming":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="programming_not_supported",
        )
    if patch.get("kind") == "vocabulary":
        patch["kind"] = "language"
    updated = await projects_repo.update(session, item, **patch)
    await home_service.invalidate_home_cache(user.id)
    return ProjectOut.model_validate(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    deleted = await projects_repo.delete_by_id(session, project_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await home_service.invalidate_home_cache(user.id)
