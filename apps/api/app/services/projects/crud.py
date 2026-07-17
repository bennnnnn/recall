"""Router-facing Learning project list / create / detail surface."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project, ProjectItem, User
from app.models.schemas import ProjectItemOut, ProjectListGroup, ProjectStats
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services.projects import stats as project_stats
from app.services.projects.common import (
    DEFAULT_LIST,
    LEARNING_PRODUCT_KINDS,
    _is_trivia_project,
    is_learning_product_kind,
    normalize_project_kind,
)
from app.services.projects.prompt_context import _stats_for_items


def group_items(items: list[ProjectItem]) -> list[ProjectListGroup]:
    by_list: dict[str, list[ProjectItem]] = {}
    for item in items:
        lst = item.list_title.strip() or DEFAULT_LIST
        by_list.setdefault(lst, []).append(item)
    groups: list[ProjectListGroup] = []
    for list_title in sorted(by_list.keys(), key=str.casefold):
        groups.append(
            ProjectListGroup(
                list_title=list_title,
                items=[ProjectItemOut.model_validate(i) for i in by_list[list_title]],
            )
        )
    return groups


def group_trivia_items(items: list[ProjectItem]) -> list[ProjectListGroup]:
    """Group saved quiz facts by topic (list_title)."""
    return group_items(items)


def build_stats(items: list[ProjectItem]) -> ProjectStats:
    raw = _stats_for_items(items)
    return ProjectStats.model_validate(raw)


def _build_enriched_stats(
    project: Project,
    items: list[ProjectItem],
    *,
    timezone_name: str,
    daily_goal_history: list[dict[str, int | str]] | None = None,
    daily_history: list[dict[str, object]] | None = None,
) -> ProjectStats:
    from app.services import daily_learning, learning_insights

    raw = project_stats.stats_from_items(items, timezone_name=timezone_name)
    if daily_history is None:
        daily_history = daily_learning.build_daily_history(
            items,
            timezone_name=timezone_name,
            daily_goal=daily_learning.resolve_daily_goal(project),
            active_since=project.created_at,
            daily_goal_history=daily_goal_history,
        )
    enriched = learning_insights.enrich_learning_stats(
        raw,
        project=project,
        items=items,
        timezone_name=timezone_name,
        daily_history=daily_history,
    )
    return ProjectStats.model_validate(enriched)


async def _resolve_daily_goal_history(
    project: Project,
    items: list[ProjectItem],
    *,
    timezone_name: str,
) -> list[dict[str, int | str]]:
    """Compute (in-memory only) goal history for stats — read path must not write.

    BUG FIX (dead code): this used to take a `persist: bool = False` parameter meant
    to cache the inferred backfill onto the project row, but every call site passed
    persist=False (get_project_detail never opted in), so the persistence branch was
    unreachable. Removed rather than wired up — caching here would mean writing on a
    GET, which the caller's own comment says a read path must not do.
    """
    from app.services import daily_learning

    return daily_learning.ensure_daily_goal_history(
        project,
        items,
        timezone_name=timezone_name,
    )


async def list_projects_for_user(
    session: AsyncSession,
    user: User,
    *,
    client_timezone: str | None = None,
) -> list[dict[str, Any]]:
    """Return product learning projects (language + trivia) with optional stats."""
    from app.services import time_context as time_context_service

    items = await projects_repo.list_for_user(session, user.id)
    visible = [item for item in items if is_learning_product_kind(item.kind)]
    learning_ids = [item.id for item in visible]
    stats_by_project: dict[UUID, ProjectStats] = {}
    if learning_ids:
        tz_name = time_context_service.effective_timezone(user.timezone, client_timezone)
        raw_stats = await project_stats.count_stats_by_project(
            session,
            learning_ids,
            timezone_by_project={pid: tz_name for pid in learning_ids},
        )
        stats_by_project = {
            pid: ProjectStats.model_validate(raw_stats.get(pid, {})) for pid in learning_ids
        }
    return [
        {
            **{
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "kind": normalize_project_kind(item.kind),
                "target_language": item.target_language,
                "native_language": item.native_language,
                "level": item.level,
                "daily_goal": item.daily_goal,
                "archived": item.archived,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            },
            "stats": stats_by_project.get(item.id),
        }
        for item in visible
    ]


async def create_learning_project(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    description: str | None,
    kind: str,
    target_language: str = "en",
    native_language: str | None = None,
    level: str = "level1",
    daily_goal: int | None = None,
) -> Project:
    """Create a language or trivia project; raises ValueError with a stable code."""
    from app.services import time_context as time_context_service

    normalized = normalize_project_kind(kind)
    if normalized not in LEARNING_PRODUCT_KINDS:
        raise ValueError("unsupported_project_kind")
    if normalized == "language":
        existing = await projects_repo.find_language_by_target(session, user.id, target_language)
        if existing:
            raise ValueError("language_project_exists")
    if normalized == "trivia":
        existing = await projects_repo.find_trivia_project(session, user.id)
        if existing:
            raise ValueError("trivia_project_exists")
    return await projects_repo.create(
        session,
        user_id=user.id,
        title=title,
        description=description,
        kind=normalized,
        target_language=target_language,
        native_language=native_language,
        level=level,
        daily_goal=daily_goal if normalized in LEARNING_PRODUCT_KINDS else None,
        timezone_name=time_context_service.effective_timezone(user.timezone, None),
    )


async def get_project_detail(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    *,
    client_timezone: str | None = None,
    include_lists: bool = False,
) -> dict[str, Any] | None:
    """Assemble project detail for language/trivia; None if missing or unsupported.

    Default response includes stats, 14-day count history, and recent day item maps
    built from the same in-memory item load (no extra queries). Full deck ``lists``
    stay omitted unless ``include_lists=True`` (PDF export).
    """
    from app.models.schemas import ProjectDailyHistoryDay, ProjectItemOut, ProjectOut
    from app.services import daily_learning
    from app.services import time_context as time_context_service

    item = await projects_repo.get_by_id(session, project_id, user.id)
    if item is None or not is_learning_product_kind(item.kind):
        return None

    tz_name = time_context_service.effective_timezone(user.timezone, client_timezone)
    project_items = await project_items_repo.list_for_user(
        session, user.id, project_id=project_id, limit=5000
    )
    # BUG FIX (was silent): day-attribution used to read last_incorrect_at, a single
    # mutable column, so a later miss on an item silently erased which day an earlier
    # miss belonged to. Load the append-only miss-event log so past days stay stable.
    miss_events_by_item = await project_items_repo.list_miss_events_for_items(
        session, [i.id for i in project_items]
    )
    # Read path must not write — compute history in memory only.
    goal_history = await _resolve_daily_goal_history(item, project_items, timezone_name=tz_name)
    history_rows = daily_learning.build_daily_history(
        project_items,
        timezone_name=tz_name,
        daily_goal=daily_learning.resolve_daily_goal(item),
        active_since=item.created_at,
        daily_goal_history=goal_history,
        days=14,
        miss_events_by_item=miss_events_by_item,
    )
    stats = _build_enriched_stats(
        item,
        project_items,
        timezone_name=tz_name,
        daily_goal_history=goal_history,
        daily_history=history_rows,
    )
    daily_history = [ProjectDailyHistoryDay.model_validate(row) for row in history_rows]
    # Recent activity only (not the full deck) — cheap to serialize from items
    # already loaded for stats, and lets the detail screen paint without a
    # second /daily-items round trip.
    daily_items_by_date = {
        day_key: [ProjectItemOut.model_validate(i) for i in day_items]
        for day_key, day_items in daily_learning.group_mastered_items_by_date(
            project_items, timezone_name=tz_name, days=14
        ).items()
    }
    daily_missed_by_date = {
        day_key: [ProjectItemOut.model_validate(i) for i in day_items]
        for day_key, day_items in daily_learning.group_missed_items_by_date(
            project_items, timezone_name=tz_name, days=14, miss_events_by_item=miss_events_by_item
        ).items()
    }
    lists: list[Any] = []
    if include_lists:
        lists = (
            group_trivia_items(project_items)
            if _is_trivia_project(item)
            else group_items(project_items)
        )
    return {
        **ProjectOut.model_validate(item).model_dump(),
        "kind": normalize_project_kind(item.kind),
        "mastered_count": stats.mastered_count,
        "total_count": stats.total,
        "stats": stats,
        "daily_history": daily_history,
        "daily_items_by_date": daily_items_by_date,
        "daily_missed_by_date": daily_missed_by_date,
        "lists": lists,
    }
