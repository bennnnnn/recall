"""SQL activity aggregates shared by both Learning stats queries."""

from datetime import datetime
from typing import Any

from sqlalchemy import case, func, or_

from app.models.orm import ProjectItem


def _latest(left: Any, right: Any) -> Any:
    return case(
        (left.is_(None), right), (right.is_(None), left), (left >= right, left), else_=right
    )


def activity_columns(start: datetime, mastered_cond: Any) -> tuple[Any, ...]:
    completed = or_(
        ProjectItem.last_completed_at >= start,
        mastered_cond & (func.coalesce(ProjectItem.mastered_at, ProjectItem.created_at) >= start),
    )
    mastery = case(
        (mastered_cond, func.coalesce(ProjectItem.mastered_at, ProjectItem.created_at)),
        else_=ProjectItem.mastered_at,
    )
    last_study = _latest(
        _latest(ProjectItem.last_reviewed_at, mastery), ProjectItem.last_incorrect_at
    )
    return (
        func.count().filter(completed).label("completed_today"),
        func.count().filter(last_study >= start).label("attempted_today"),
        func.count().filter(ProjectItem.last_incorrect_at >= start).label("incorrect_today"),
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
