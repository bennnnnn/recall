"""SQL activity aggregates shared by both Learning stats queries."""

from datetime import datetime
from typing import Any

from sqlalchemy import case, func, or_

from app.models.orm import LearningItem


def _latest(left: Any, right: Any) -> Any:
    return case(
        (left.is_(None), right), (right.is_(None), left), (left >= right, left), else_=right
    )


def activity_columns(start: datetime, mastered_cond: Any) -> tuple[Any, ...]:
    completed = or_(
        LearningItem.last_completed_at >= start,
        mastered_cond & (func.coalesce(LearningItem.mastered_at, LearningItem.created_at) >= start),
    )
    mastery = case(
        (mastered_cond, func.coalesce(LearningItem.mastered_at, LearningItem.created_at)),
        else_=LearningItem.mastered_at,
    )
    last_study = _latest(
        _latest(LearningItem.last_reviewed_at, mastery), LearningItem.last_incorrect_at
    )
    return (
        func.count().filter(completed).label("completed_today"),
        func.count().filter(last_study >= start).label("attempted_today"),
        func.count().filter(LearningItem.last_incorrect_at >= start).label("incorrect_today"),
        func.max(last_study).label("last_study_at"),
    )


def activity_values(row: Any) -> dict[str, Any]:
    return {
        "completed_today": row.completed_today or 0,
        "attempted_today": row.attempted_today or 0,
        "incorrect_today": row.incorrect_today or 0,
        "newly_mastered_today": row.mastered_today or 0,
        "last_study_at": row.last_study_at,
    }
