"""Streak, nudge scoring, and adaptive level helpers for learning projects."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.models.orm import Project

LEARNING_PROJECT_KINDS = ("language", "vocabulary", "trivia")
LEVEL_ORDER = ("level1", "level2", "level3", "level4", "level5", "level6")
SuggestedLevel = Literal["up", "down"]
NudgeType = Literal["learning_daily_goal", "learning_review", "learning_continue"]


def is_learning_project_kind(kind: str | None) -> bool:
    return kind in LEARNING_PROJECT_KINDS


def days_since_last_study(
    last_mastery: datetime | None,
    *,
    home_tz: ZoneInfo,
) -> int | None:
    if last_mastery is None:
        return None
    today = datetime.now(home_tz).date()
    last_day = last_mastery.astimezone(home_tz).date()
    return max(0, (today - last_day).days)


def compute_streak_days(history: list[dict[str, Any]]) -> int:
    """Consecutive goal-met days ending today or the most recent active day."""
    streak = 0
    saw_today = False
    for day in reversed(history):
        status = day.get("status")
        if status == "inactive":
            continue
        if status == "today":
            saw_today = True
            if day.get("goal_met"):
                streak += 1
            continue
        if day.get("goal_met"):
            streak += 1
        elif saw_today:
            continue
        else:
            break
    return streak


def quiz_accuracy_pct(items: list[Any], *, min_attempts: int = 8) -> int | None:
    attempts = sum(int(getattr(item, "quiz_attempts", 0) or 0) for item in items)
    correct = sum(int(getattr(item, "quiz_correct", 0) or 0) for item in items)
    if attempts < min_attempts:
        return None
    return round(100 * correct / attempts)


def suggest_level_change(project: Project, stats: dict[str, Any]) -> SuggestedLevel | None:
    if project.kind not in ("language", "vocabulary"):
        return None
    total = int(stats.get("total") or 0)
    if total < 25:
        return None
    level = (project.level or "level1").strip()
    idx = LEVEL_ORDER.index(level) if level in LEVEL_ORDER else 0
    mastered = int(stats.get("mastered_count") or 0)
    ratio = mastered / total
    accuracy = stats.get("quiz_accuracy_pct")
    if ratio >= 0.88 and (accuracy is None or accuracy >= 78) and idx < len(LEVEL_ORDER) - 1:
        return "up"
    if (
        ratio < 0.45
        and int(stats.get("learning_count") or 0) > int(stats.get("new_count") or 0)
        and (accuracy is None or accuracy < 55)
        and idx > 0
    ):
        return "down"
    return None


def enrich_learning_stats(
    stats: dict[str, Any],
    *,
    project: Project,
    items: list[Any],
    timezone_name: str,
    daily_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    try:
        home_tz = ZoneInfo(timezone_name)
    except Exception:
        home_tz = ZoneInfo("UTC")
    last_mastery = stats.get("last_mastery_at")
    if isinstance(last_mastery, datetime):
        stats["days_inactive"] = days_since_last_study(last_mastery, home_tz=home_tz)
    else:
        stats["days_inactive"] = None
    if daily_history is not None:
        stats["streak_days"] = compute_streak_days(daily_history)
    else:
        stats["streak_days"] = 0
    stats["quiz_accuracy_pct"] = quiz_accuracy_pct(items)
    stats["suggested_level"] = suggest_level_change(project, stats)
    return stats


def _unit_label(kind: str | None, *, plural: bool = True) -> str:
    if kind == "trivia":
        return "questions" if plural else "question"
    return "words" if plural else "word"


def pick_learning_nudge(
    project: Project,
    stats: dict[str, Any],
    *,
    daily_goal: int,
) -> tuple[str, float, NudgeType, dict[str, str]] | None:
    """Return body, score, nudge type, and push payload fields."""
    if int(stats.get("total") or 0) == 0:
        return None

    kind = project.kind
    unit = _unit_label(kind)
    mastered_today = int(stats.get("mastered_today") or 0)
    due = int(stats.get("due_for_review") or 0)
    new_count = int(stats.get("new_count") or 0)
    days_inactive = stats.get("days_inactive")
    title = project.title.strip()

    if mastered_today < daily_goal:
        remaining = daily_goal - mastered_today
        inactive_note = ""
        if isinstance(days_inactive, int) and days_inactive >= 2:
            inactive_note = f" — you have not studied in {days_inactive} days"
        body = (
            f'Finish today\'s "{title}" session — '
            f"{mastered_today}/{daily_goal} {unit}{inactive_note}"
        )
        score = 55.0 + float(remaining)
        return (
            body,
            score,
            "learning_daily_goal",
            {
                "type": "learning_daily_goal",
                "screen": "project",
                "project_id": str(project.id),
            },
        )

    if due > 0:
        unit = _unit_label(kind, plural=due != 1)
        body = f'{due} {unit} due for review in "{title}"'
        score = float(due + 10)
        return (
            body,
            score,
            "learning_review",
            {
                "type": "learning_review",
                "screen": "project",
                "project_id": str(project.id),
            },
        )

    if new_count > 0:
        body = f'Keep going with "{title}" — {new_count} new {_unit_label(kind)}'
        score = float(new_count)
        return (
            body,
            score,
            "learning_continue",
            {
                "type": "learning_continue",
                "screen": "project",
                "project_id": str(project.id),
            },
        )

    return None


def best_learning_nudge_for_user(
    projects: list[Project],
    stats_by_project: dict[UUID, dict[str, Any]],
    *,
    daily_goal_for: Any,
) -> tuple[Project, str, float, NudgeType, dict[str, str]] | None:
    best: tuple[Project, str, float, NudgeType, dict[str, str]] | None = None
    for project in projects:
        if not is_learning_project_kind(project.kind):
            continue
        stats = stats_by_project.get(project.id)
        if stats is None:
            continue
        daily_goal = daily_goal_for(project)
        picked = pick_learning_nudge(project, stats, daily_goal=daily_goal)
        if picked is None:
            continue
        body, score, nudge_type, payload = picked
        if best is None or score > best[2]:
            best = (project, body, score, nudge_type, payload)
    return best
