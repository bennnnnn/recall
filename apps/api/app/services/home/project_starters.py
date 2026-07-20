"""Learning-project home starters and highlight card."""

from __future__ import annotations

from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project
from app.models.schemas import HomeProjectHighlight, ProjectStats
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services import daily_learning, learning_insights
from app.services.home.util import CompletedDaily, ProjectHomeContent
from app.services.projects import stats as project_stats


def is_language_project(project: Project) -> bool:
    return project.kind in ("language", "vocabulary")


def is_trivia_project(project: Project) -> bool:
    return project.kind == "trivia"


def is_daily_home_project(project: Project) -> bool:
    return is_language_project(project) or is_trivia_project(project)


def daily_home_kind(project: Project) -> Literal["language", "trivia"]:
    return "trivia" if is_trivia_project(project) else "language"


def completed_today(stats: ProjectStats) -> int:
    return max(0, int(stats.mastered_today) + int(getattr(stats, "missed_today", 0) or 0))


def project_highlight(
    project: Project,
    stats: ProjectStats,
    *,
    home_tz: ZoneInfo,
    project_items: list | None = None,
) -> HomeProjectHighlight | None:
    if not is_daily_home_project(project):
        return None
    daily_goal = daily_learning.resolve_daily_goal(project)
    cue = daily_learning.daily_home_cue(
        total=stats.total,
        mastered_today=stats.mastered_today,
        missed_today=int(getattr(stats, "missed_today", 0) or 0),
        pending_today=stats.pending_today,
        learning_count=stats.learning_count,
        due_for_review=stats.due_for_review,
        daily_goal=daily_goal,
        last_mastery=stats.last_mastery_at,
        home_tz=home_tz,
    )
    if cue is None:
        return None
    enriched = learning_insights.enrich_learning_stats(
        stats.model_dump(),
        project=project,
        items=project_items or [],
        timezone_name=str(home_tz.key),
        daily_history=daily_learning.build_daily_history(
            project_items or [],
            timezone_name=str(home_tz.key),
            daily_goal=daily_goal,
            active_since=project.created_at,
            daily_goal_history=daily_learning.ensure_daily_goal_history(
                project,
                project_items or [],
                timezone_name=str(home_tz.key),
            ),
        )
        if project_items
        else None,
    )
    return HomeProjectHighlight(
        project_id=project.id,
        title=project.title.strip(),
        kind=daily_home_kind(project),
        daily_goal=daily_goal,
        mastered_today=stats.mastered_today,
        missed_today=int(getattr(stats, "missed_today", 0) or 0),
        cue=cue,
        streak_days=int(enriched.get("streak_days") or 0),
        days_inactive=enriched.get("days_inactive"),
        due_for_review=stats.due_for_review,
        suggested_level=enriched.get("suggested_level"),
    )


async def load_project_home_content(
    session: AsyncSession,
    user_id: UUID,
    *,
    home_tz: ZoneInfo,
) -> ProjectHomeContent:
    projects = await projects_repo.list_for_user(session, user_id, limit=20)
    has_language = any(is_language_project(p) for p in projects)
    if not projects:
        return ProjectHomeContent([], None, None, [], False)

    daily_projects = sorted(
        [p for p in projects if is_daily_home_project(p)],
        key=lambda p: (0 if is_language_project(p) else 1, p.title.casefold()),
    )
    tz_name = str(home_tz.key)

    if daily_projects:
        project_ids = [candidate.id for candidate in daily_projects]
        # One item fetch for all daily projects — reuse for stats + highlight enrich.
        all_items = await project_items_repo.list_for_projects(session, project_ids)
        items_by_project: dict[UUID, list] = {pid: [] for pid in project_ids}
        for row in all_items:
            items_by_project.setdefault(row.project_id, []).append(row)
        stats_by_project = {
            pid: project_stats.stats_from_items(
                items_by_project.get(pid, []),
                timezone_name=tz_name,
            )
            for pid in project_ids
        }
        completed_daily: list[CompletedDaily] = []
        for candidate in daily_projects:
            stats = ProjectStats.model_validate(stats_by_project.get(candidate.id, {}))
            daily_goal = daily_learning.resolve_daily_goal(candidate)
            if completed_today(stats) >= daily_goal:
                completed_daily.append((candidate.title.strip(), daily_home_kind(candidate)))
                continue
            # Cue can be decided from stats alone; only enrich the first highlight.
            cue = daily_learning.daily_home_cue(
                total=stats.total,
                mastered_today=stats.mastered_today,
                missed_today=int(getattr(stats, "missed_today", 0) or 0),
                pending_today=stats.pending_today,
                learning_count=stats.learning_count,
                due_for_review=stats.due_for_review,
                daily_goal=daily_goal,
                last_mastery=stats.last_mastery_at,
                home_tz=home_tz,
            )
            if cue is None:
                continue
            project_items = items_by_project.get(candidate.id, [])
            highlight = project_highlight(
                candidate,
                stats,
                home_tz=home_tz,
                project_items=project_items,
            )
            if highlight is not None:
                # Project chip starters were removed — highlight card is the only
                # learning CTA on home (do not reintroduce Start/Continue chips).
                return ProjectHomeContent([], None, highlight, completed_daily, has_language)
        return ProjectHomeContent([], None, None, completed_daily, has_language)

    # No English/trivia daily cue — do not fall back to legacy project kinds
    # (old programming topics used to show up as "Continue TypeScript · …").
    return ProjectHomeContent([], None, None, [], has_language)
