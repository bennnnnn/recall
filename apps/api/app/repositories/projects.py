from datetime import datetime
from types import SimpleNamespace
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project
from app.services import daily_learning


def _initial_daily_goal_history(
    *,
    kind: str,
    daily_goal: int | None,
    timezone_name: str,
) -> list[dict[str, int | str]] | None:
    if kind not in ("language", "trivia"):
        return None
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    goal = daily_learning.resolve_daily_goal(SimpleNamespace(kind=kind, daily_goal=daily_goal))
    return [{"effective_from": today.isoformat(), "goal": goal}]


async def list_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    include_archived: bool = False,
    limit: int = 200,
) -> list[Project]:
    stmt = select(Project).where(Project.user_id == user_id)
    if not include_archived:
        stmt = stmt.where(Project.archived.is_(False))
    stmt = stmt.order_by(Project.updated_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def list_for_users(
    session: AsyncSession,
    user_ids: list[UUID],
    *,
    include_archived: bool = False,
) -> list[Project]:
    """Batched list_for_user — one query across many users instead of one per user."""
    if not user_ids:
        return []
    stmt = select(Project).where(Project.user_id.in_(user_ids))
    if not include_archived:
        stmt = stmt.where(Project.archived.is_(False))
    return list((await session.execute(stmt)).scalars().all())


async def get_by_id(session: AsyncSession, project_id: UUID, user_id: UUID) -> Project | None:
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_language_by_target(
    session: AsyncSession,
    user_id: UUID,
    target_language: str,
) -> Project | None:
    lang = (target_language or "en").strip().lower()
    stmt = (
        select(Project)
        .where(
            Project.user_id == user_id,
            Project.archived.is_(False),
            Project.kind.in_(("language", "vocabulary")),
            Project.target_language == lang,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_trivia_project(session: AsyncSession, user_id: UUID) -> Project | None:
    stmt = (
        select(Project)
        .where(
            Project.user_id == user_id,
            Project.archived.is_(False),
            Project.kind == "trivia",
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    user_id: UUID,
    title: str,
    description: str | None = None,
    kind: str = "language",
    target_language: str = "en",
    native_language: str | None = None,
    level: str = "level1",
    daily_goal: int | None = None,
    timezone_name: str = "UTC",
) -> Project:
    normalized_kind = "language" if kind == "vocabulary" else kind
    project = Project(
        user_id=user_id,
        title=title,
        description=description,
        kind=normalized_kind,
        target_language=(target_language or "en").strip().lower(),
        native_language=native_language,
        level=level,
        daily_goal=daily_goal,
        daily_goal_history=_initial_daily_goal_history(
            kind=normalized_kind,
            daily_goal=daily_goal,
            timezone_name=timezone_name,
        ),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def update(session: AsyncSession, project: Project, **fields: object) -> Project:
    for key, value in fields.items():
        setattr(project, key, value)
    await session.commit()
    await session.refresh(project)
    return project


async def delete_by_id(session: AsyncSession, project_id: UUID, user_id: UUID) -> bool:
    project = await get_by_id(session, project_id, user_id)
    if not project:
        return False
    await session.delete(project)
    await session.commit()
    return True
