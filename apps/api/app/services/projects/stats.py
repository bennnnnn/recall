"""Project-item stats aggregation (pure + load wrappers)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProjectItem
from app.repositories import project_items as project_items_repo

REVIEW_INTERVAL = timedelta(hours=24)  # legacy fallback when due_at is unset


def stats_from_items(
    items: list[ProjectItem],
    *,
    timezone_name: str = "UTC",
) -> dict[str, int]:
    from app.services.daily_learning import count_today_vocab_stats, last_mastery_at

    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    due_cutoff = now - REVIEW_INTERVAL
    stats: dict[str, Any] = {
        "total": len(items),
        "new_count": 0,
        "learning_count": 0,
        "mastered_count": 0,
        "added_this_week": 0,
        "due_for_review": 0,
        "mastered_today": 0,
        "missed_today": 0,
        "pending_today": 0,
        "last_mastery_at": None,
    }
    for item in items:
        status = item.status or ("mastered" if item.mastered else "new")
        if status == "mastered":
            stats["mastered_count"] += 1
        elif status == "learning":
            stats["learning_count"] += 1
        else:
            stats["new_count"] += 1
        created = item.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created >= week_ago:
            stats["added_this_week"] += 1
        if status == "learning":
            due_at = item.due_at
            if due_at is None:
                last = item.last_reviewed_at or item.created_at
                if last and last.tzinfo is None:
                    last = last.replace(tzinfo=UTC)
                if last and last <= due_cutoff:
                    stats["due_for_review"] += 1
            elif due_at.tzinfo is None:
                if due_at.replace(tzinfo=UTC) <= now:
                    stats["due_for_review"] += 1
            elif due_at <= now:
                stats["due_for_review"] += 1

    mastered_today, missed_today, pending_today = count_today_vocab_stats(
        items, timezone_name=timezone_name
    )
    stats["mastered_today"] = mastered_today
    stats["missed_today"] = missed_today
    stats["pending_today"] = pending_today
    stats["last_mastery_at"] = last_mastery_at(items)
    return stats


async def count_stats(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    *,
    timezone_name: str = "UTC",
) -> dict[str, int]:
    items = await project_items_repo.list_for_user(
        session, user_id, project_id=project_id, limit=5000
    )
    return stats_from_items(items, timezone_name=timezone_name)


async def count_stats_by_project(
    session: AsyncSession,
    project_ids: list[UUID],
    *,
    timezone_by_project: dict[UUID, str] | None = None,
) -> dict[UUID, dict[str, int]]:
    if not project_ids:
        return {}
    items = await project_items_repo.list_for_projects(session, project_ids)
    by_project: dict[UUID, list[ProjectItem]] = {pid: [] for pid in project_ids}
    for item in items:
        by_project.setdefault(item.project_id, []).append(item)
    tz_by_project = timezone_by_project or {}
    return {
        pid: stats_from_items(pid_items, timezone_name=tz_by_project.get(pid, "UTC"))
        for pid, pid_items in by_project.items()
    }
