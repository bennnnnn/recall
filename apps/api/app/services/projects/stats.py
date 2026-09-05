"""Project-item stats aggregation (pure + load wrappers)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.learning_policy import start_of_today_utc
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
    start = start_of_today_utc(timezone_name, now=now)
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
        "completed_today": 0,
        "attempted_today": 0,
        "incorrect_today": 0,
        "last_study_at": None,
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
        if status in ("learning", "mastered"):
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
        mastery = (
            (item.mastered_at or item.created_at) if status == "mastered" else item.mastered_at
        )
        times = [
            value.replace(tzinfo=UTC) if value.tzinfo is None else value
            for value in (item.last_reviewed_at, mastery, item.last_incorrect_at)
            if isinstance(value, datetime)
        ]
        if times:
            latest = max(times)
            stats["last_study_at"] = max(stats["last_study_at"] or latest, latest)
            stats["attempted_today"] += int(latest >= start)
        completed = getattr(item, "last_completed_at", None)
        completions = [
            value.replace(tzinfo=UTC) if value.tzinfo is None else value
            for value in (completed, mastery if status == "mastered" else None)
            if isinstance(value, datetime)
        ]
        stats["completed_today"] += int(bool(completions) and max(completions) >= start)
        incorrect = item.last_incorrect_at
        if isinstance(incorrect, datetime):
            incorrect = incorrect.replace(tzinfo=UTC) if incorrect.tzinfo is None else incorrect
            stats["incorrect_today"] += int(incorrect >= start)

    mastered_today, missed_today, pending_today = count_today_vocab_stats(
        items, timezone_name=timezone_name
    )
    stats["mastered_today"] = mastered_today
    stats["newly_mastered_today"] = mastered_today
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
    """Per-project stats via SQL aggregates — no item loading, no truncation.

    (LANG-FLOW-002) Replaces the load-all-then-count pattern that capped at
    5k items and silently under-counted large decks.
    """
    return await project_items_repo.count_stats_sql(
        session, project_id, user_id, timezone_name=timezone_name
    )


async def count_stats_by_project(
    session: AsyncSession,
    project_ids: list[UUID],
    *,
    timezone_by_project: dict[UUID, str] | None = None,
) -> dict[UUID, dict[str, int]]:
    """Per-project stats via SQL — no global cap, no truncation.

    (LANG-FLOW-001) Replaces the batched load-all pattern that capped at 20k
    across all projects with no per-project window.
    """
    return await project_items_repo.count_stats_by_project_sql(
        session, project_ids, timezone_by_project=timezone_by_project
    )
