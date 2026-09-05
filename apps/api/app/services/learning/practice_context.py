"""Compact, factual Learning activity for ordinary chat questions."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project, ProjectItem
from app.repositories import learning_practice as practice_repo
from app.repositories import project_items as items_repo
from app.services.learning.daily import (
    build_daily_history,
    parse_daily_goal_history,
    resolve_daily_goal,
)
from app.services.learning.practice_history import merge_practice_history
from app.services.projects.stats import stats_from_items


async def load_activity_context(
    session: AsyncSession,
    projects: list[Project],
    items: list[ProjectItem],
    *,
    timezone_name: str,
) -> str:
    since = datetime.now(UTC) - timedelta(days=8)
    events = await practice_repo.list_events(
        session, [project.id for project in projects], since=since
    )
    visible_item_ids = {item.id for item in items}
    events = [event for event in events if event.item_id in visible_item_ids]
    misses = await items_repo.list_miss_events_for_items(
        session, [item.id for item in items], since=since
    )
    by_project: dict[UUID, list[ProjectItem]] = {project.id: [] for project in projects}
    for item in items:
        if item.project_id in by_project:
            by_project[item.project_id].append(item)
    lines = ["Saved Learning activity (authoritative; first mastery and practice are different):"]
    for project in projects:
        words = by_project[project.id]
        stats = stats_from_items(words, timezone_name=timezone_name)
        goal = resolve_daily_goal(project)
        lines.append(
            f"- {project.title}: today {stats['completed_today']}/{goal} words completed "
            f"(including reviews), {stats['attempted_today']} attempted, "
            f"{stats['newly_mastered_today']} newly mastered, "
            f"{stats['incorrect_today']} answered incorrectly; "
            f"{stats['due_for_review']} words currently due for review."
        )
        history = build_daily_history(
            words,
            timezone_name=timezone_name,
            daily_goal=goal,
            active_since=project.created_at,
            days=7,
            miss_events_by_item=misses,
            daily_goal_history=parse_daily_goal_history(project),
        )
        project_events = [event for event in events if event.project_id == project.id]
        history = merge_practice_history(
            history, words, project_events, timezone_name=timezone_name, miss_events_by_item=misses
        )
        skipped = [str(row["date"]) for row in history if row["status"] == "skipped"]
        lines.append(
            f"  Recent days with no recorded practice: {', '.join(skipped) if skipped else 'none'}."
        )
        lines.append(f"  Last recorded study: {stats['last_study_at'] or 'none yet'}.")
    lines.append(
        "Use saved activity to discuss missed practice. "
        "Do not invent which individual reviews were skipped on past dates."
    )
    return "\n".join(lines)
