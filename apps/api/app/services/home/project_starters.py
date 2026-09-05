"""Learning-project home starters and highlight card."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import LearningPracticeEvent, Project
from app.models.schemas import HomeProjectHighlight, ProjectStats
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services import daily_learning, learning_insights
from app.services.home.util import CompletedDaily, ProjectHomeContent
from app.services.projects import stats as project_stats
from app.services.projects.common import normalize_target_language


def is_language_project(project: Project) -> bool:
    return project.kind in ("language", "vocabulary")


def is_daily_home_project(project: Project) -> bool:
    return is_language_project(project)


def daily_home_kind(project: Project) -> Literal["language"]:
    return "language"


def completed_today(stats: ProjectStats) -> int:
    if "completed_today" in stats.model_fields_set:
        return stats.completed_today
    return max(0, int(stats.mastered_today) + int(getattr(stats, "missed_today", 0) or 0))


def project_highlight(
    project: Project,
    stats: ProjectStats,
    *,
    home_tz: ZoneInfo,
    project_items: list | None = None,
    miss_events_by_item: dict[Any, list[datetime]] | None = None,
    practice_events: list[LearningPracticeEvent] | None = None,
) -> HomeProjectHighlight | None:
    if not is_daily_home_project(project):
        return None
    daily_goal = daily_learning.resolve_daily_goal(project)
    cue = daily_learning.daily_home_cue(
        completed_words=completed_today(stats),
        attempted_words=stats.attempted_today,
        total=stats.total,
        mastered_today=stats.mastered_today,
        missed_today=int(getattr(stats, "missed_today", 0) or 0),
        pending_today=stats.pending_today,
        learning_count=stats.learning_count,
        due_for_review=stats.due_for_review,
        daily_goal=daily_goal,
        last_mastery=stats.last_study_at or stats.last_mastery_at,
        home_tz=home_tz,
    )
    if cue is None:
        return None
    from app.services.learning.practice_history import merge_practice_history

    enriched = learning_insights.enrich_learning_stats(
        stats.model_dump(),
        project=project,
        items=project_items or [],
        timezone_name=str(home_tz.key),
        daily_history=merge_practice_history(
            daily_learning.build_daily_history(
                project_items or [],
                timezone_name=str(home_tz.key),
                daily_goal=daily_goal,
                active_since=project.created_at,
                daily_goal_history=daily_learning.ensure_daily_goal_history(
                    project,
                    project_items or [],
                    timezone_name=str(home_tz.key),
                ),
                miss_events_by_item=miss_events_by_item,
            ),
            project_items or [],
            practice_events or [],
            timezone_name=str(home_tz.key),
            miss_events_by_item=miss_events_by_item,
        )
        if project_items
        else None,
    )
    return HomeProjectHighlight(
        project_id=project.id,
        title=project.title.strip(),
        kind=daily_home_kind(project),
        target_language=normalize_target_language(getattr(project, "target_language", None))
        or "en",
        daily_goal=daily_goal,
        mastered_today=stats.mastered_today,
        completed_today=completed_today(stats),
        attempted_today=stats.attempted_today,
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
                completed_words=completed_today(stats),
                attempted_words=stats.attempted_today,
                total=stats.total,
                mastered_today=stats.mastered_today,
                missed_today=int(getattr(stats, "missed_today", 0) or 0),
                pending_today=stats.pending_today,
                learning_count=stats.learning_count,
                due_for_review=stats.due_for_review,
                daily_goal=daily_goal,
                last_mastery=stats.last_study_at or stats.last_mastery_at,
                home_tz=home_tz,
            )
            if cue is None:
                continue
            project_items = items_by_project.get(candidate.id, [])
            # Load miss events so daily history attributes misses to every day
            # they occurred on, including items later mastered (LANG-BE-005/007).
            item_ids = [it.id for it in project_items if hasattr(it, "id")]
            miss_events = await project_items_repo.list_miss_events_for_items(session, item_ids)
            from app.repositories import learning_practice as practice_repo

            practice_events = await practice_repo.list_events(
                session, [candidate.id], since=datetime.now(UTC) - timedelta(days=15)
            )
            highlight = project_highlight(
                candidate,
                stats,
                home_tz=home_tz,
                project_items=project_items,
                miss_events_by_item=miss_events,
                practice_events=practice_events,
            )
            if highlight is not None:
                # Project chip starters were removed — highlight card is the only
                # learning CTA on home (do not reintroduce Start/Continue chips).
                return ProjectHomeContent([], None, highlight, completed_daily, has_language)
        return ProjectHomeContent([], None, None, completed_daily, has_language)

    # No English daily cue — do not fall back to legacy project kinds
    # (old programming topics used to show up as "Continue TypeScript · …").
    return ProjectHomeContent([], None, None, [], has_language)
