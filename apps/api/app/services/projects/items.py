"""Project-item create/update and daily activity list wrappers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProjectItem, QuizMissEvent
from app.repositories import project_items as project_items_repo
from app.repositories.project_items import DEFAULT_LIST
from app.services.daily_learning import day_bounds_utc
from app.services.sm2 import apply_sm2, quality_for_status


async def create_item(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    content: str,
    list_title: str = DEFAULT_LIST,
    note: str | None = None,
    definition: str | None = None,
    example_sentence: str | None = None,
    chat_id: UUID | None = None,
    status: str = "new",
    commit: bool = True,
) -> ProjectItem:
    # Do not call dictionaryapi on the quiz/turn-prep hot path — that HTTP round
    # trip blocked grading. Persist without pronunciation; fill async later if needed.
    return await project_items_repo.create(
        session,
        user_id=user_id,
        project_id=project_id,
        content=content,
        list_title=list_title,
        note=note,
        definition=definition,
        example_sentence=example_sentence,
        chat_id=chat_id,
        status=status,
        pronunciation_url=None,
        commit=commit,
    )


async def update_item(session: AsyncSession, item: ProjectItem, **fields: Any) -> ProjectItem:
    """Apply field updates; schedule SM-2 when status changes."""
    now = datetime.now(UTC)
    prior_status = item.status or ("mastered" if item.mastered else "new")
    if "status" in fields:
        new_status = str(fields["status"])
        if new_status != prior_status:
            was_correct = fields.pop("was_correct", None)
            # UI "Needs review" / Failed maps to status=learning. That must count as a
            # miss for today's Failed metric and day history — quiz grading already
            # stamps last_incorrect_at + QuizMissEvent, but manual status updates did not.
            if new_status == "learning":
                if not isinstance(was_correct, bool):
                    was_correct = False
                fields["last_incorrect_at"] = now
                session.add(QuizMissEvent(item_id=item.id, user_id=item.user_id, occurred_at=now))
            quality = quality_for_status(
                new_status,
                was_correct=was_correct if isinstance(was_correct, bool) else None,
            )
            state = apply_sm2(
                quality=quality,
                ease_factor=float(getattr(item, "ease_factor", 2.5) or 2.5),
                interval_days=int(getattr(item, "interval_days", 0) or 0),
                review_count=int(item.review_count or 0),
                now=now,
            )
            fields["last_reviewed_at"] = now
            fields["review_count"] = state.review_count
            fields["ease_factor"] = state.ease_factor
            fields["interval_days"] = state.interval_days
            fields["due_at"] = state.due_at
        else:
            fields.pop("was_correct", None)
    else:
        fields.pop("was_correct", None)
    return await project_items_repo.update(session, item, **fields)


async def list_by_activity_date(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    activity_date: date,
    *,
    timezone_name: str = "UTC",
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectItem]:
    start, end = day_bounds_utc(activity_date, timezone_name)
    return await project_items_repo.list_by_activity_date(
        session,
        user_id,
        project_id,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )


async def list_missed_by_activity_date(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    activity_date: date,
    *,
    timezone_name: str = "UTC",
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectItem]:
    start, end = day_bounds_utc(activity_date, timezone_name)
    return await project_items_repo.list_missed_by_activity_date(
        session,
        user_id,
        project_id,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )
