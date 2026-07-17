from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import User
from app.models.schemas import (
    ProjectCreate,
    ProjectDetailOut,
    ProjectItemOut,
    ProjectItemUpdate,
    ProjectListOut,
    ProjectOut,
    ProjectUpdate,
)
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services import daily_learning
from app.services import home as home_service
from app.services import projects as projects_service
from app.services import time_context as time_context_service
from app.services.projects import items as project_items_service
from app.services.projects.items import update_item

router = APIRouter(prefix="/projects", tags=["projects"])

_CREATE_ERROR_STATUS = {
    "unsupported_project_kind": status.HTTP_400_BAD_REQUEST,
    "language_project_exists": status.HTTP_409_CONFLICT,
    "trivia_project_exists": status.HTTP_409_CONFLICT,
}


def _project_timezone(user: User, client_timezone: str | None) -> str:
    return time_context_service.effective_timezone(user.timezone, client_timezone)


@router.get("", response_model=list[ProjectListOut])
async def list_projects(
    client_timezone: str | None = Query(default=None, max_length=64),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ProjectListOut]:
    rows = await projects_service.list_projects_for_user(
        session, user, client_timezone=client_timezone
    )
    return [ProjectListOut.model_validate(row) for row in rows]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    try:
        item = await projects_service.create_learning_project(
            session,
            user,
            title=body.title,
            description=body.description,
            kind=body.kind,
            target_language=body.target_language,
            native_language=body.native_language,
            level=body.level,
            daily_goal=body.daily_goal,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=_CREATE_ERROR_STATUS.get(code, status.HTTP_400_BAD_REQUEST),
            detail=code,
        ) from exc
    await home_service.invalidate_home_cache(user.id)
    return ProjectOut.model_validate(item)


@router.get("/{project_id}", response_model=ProjectDetailOut)
async def get_project(
    project_id: UUID,
    client_timezone: str | None = Query(default=None, max_length=64),
    include_lists: bool = Query(
        default=False,
        description="Include full item lists (for PDF export). Default omits the full deck; recent day maps are still included for a fast detail open.",
    ),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectDetailOut:
    detail = await projects_service.get_project_detail(
        session,
        user,
        project_id,
        client_timezone=client_timezone,
        include_lists=include_lists,
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectDetailOut.model_validate(detail)


@router.get("/{project_id}/daily-items", response_model=list[ProjectItemOut])
async def list_daily_items(
    project_id: UUID,
    activity_date: str = Query(..., min_length=10, max_length=10),
    client_timezone: str | None = Query(default=None, max_length=64),
    bucket: str = Query(
        default="mastered",
        pattern="^(mastered|missed)$",
        description="mastered = completed that day; missed = still-open misses that day",
    ),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectItemOut]:
    project = await projects_repo.get_by_id(session, project_id, user.id)
    if project is None or not projects_service.is_learning_product_kind(project.kind):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    try:
        parsed_date = date.fromisoformat(activity_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="activity_date must be YYYY-MM-DD",
        ) from exc
    tz_name = _project_timezone(user, client_timezone)
    if bucket == "missed":
        items = await project_items_service.list_missed_by_activity_date(
            session,
            user.id,
            project_id,
            parsed_date,
            timezone_name=tz_name,
            limit=limit,
            offset=offset,
        )
    else:
        items = await project_items_service.list_by_activity_date(
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
    if project is None or not projects_service.is_learning_product_kind(project.kind):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    item = await project_items_repo.get_by_id(session, item_id, user.id, project_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    updated = await update_item(session, item, **patch)
    await home_service.invalidate_home_cache(user.id)
    return ProjectItemOut.model_validate(updated)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    client_timezone: str | None = Query(default=None, max_length=64),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    item = await projects_repo.get_by_id(session, project_id, user.id)
    if item is None or not projects_service.is_learning_product_kind(item.kind):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    patch = body.model_dump(exclude_unset=True)
    if "kind" in patch:
        patch["kind"] = projects_service.normalize_project_kind(patch["kind"])
        if patch["kind"] not in projects_service.LEARNING_PRODUCT_KINDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unsupported_project_kind",
            )
    new_goal = patch.get("daily_goal")
    if isinstance(new_goal, int) and new_goal != item.daily_goal:
        tz_name = _project_timezone(user, client_timezone)
        tz = ZoneInfo(tz_name)
        today = datetime.now(tz).date()
        existing = daily_learning.parse_daily_goal_history(item)
        patch["daily_goal_history"] = daily_learning.append_daily_goal_history(
            existing or None,
            old_goal=item.daily_goal,
            new_goal=new_goal,
            project_created=item.created_at,
            effective_from=today,
            timezone_name=tz_name,
        )
    updated = await projects_repo.update(session, item, **patch)
    await home_service.invalidate_home_cache(user.id)
    return ProjectOut.model_validate(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    item = await projects_repo.get_by_id(session, project_id, user.id)
    if item is None or not projects_service.is_learning_product_kind(item.kind):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    deleted = await projects_repo.delete_by_id(session, project_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await home_service.invalidate_home_cache(user.id)
