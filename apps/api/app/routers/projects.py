from datetime import date
from uuid import UUID

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
from app.repositories import projects as projects_repo
from app.services import projects as projects_service
from app.services import time_context as time_context_service
from app.services.projects import crud as projects_crud
from app.services.projects import items as project_items_service

router = APIRouter(prefix="/projects", tags=["projects"])

_CREATE_ERROR_STATUS = {
    "unsupported_project_kind": status.HTTP_400_BAD_REQUEST,
    "unsupported_target_language": status.HTTP_400_BAD_REQUEST,
    "language_project_exists": status.HTTP_409_CONFLICT,
}


def _map_error(exc: projects_crud.ProjectsError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


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
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10_000),
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
    try:
        updated = await projects_crud.update_learning_project_item(
            session, user, project_id, item_id, body.model_dump(exclude_unset=True)
        )
    except projects_crud.ProjectsError as exc:
        raise _map_error(exc) from exc
    return ProjectItemOut.model_validate(updated)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    client_timezone: str | None = Query(default=None, max_length=64),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    try:
        updated = await projects_crud.update_learning_project(
            session,
            user,
            project_id,
            body.model_dump(exclude_unset=True),
            client_timezone=client_timezone,
        )
    except projects_crud.ProjectsError as exc:
        raise _map_error(exc) from exc
    return ProjectOut.model_validate(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await projects_crud.delete_learning_project(session, user, project_id)
    except projects_crud.ProjectsError as exc:
        raise _map_error(exc) from exc
