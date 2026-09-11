"""SM-2 quiz results from lesson practice."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import LearningItem
from app.repositories import learning_items as learning_items_repo
from app.services.sm2 import apply_sm2, quality_for_status


def _item_status_label(item: LearningItem) -> str:
    if item.status:
        return item.status
    return "mastered" if item.mastered else "new"


async def apply_quiz_result(
    session: AsyncSession,
    item: LearningItem,
    *,
    is_correct: bool,
    commit: bool = True,
) -> LearningItem:
    """Derive status + SM-2 schedule, then persist via the repository."""
    now = datetime.now(UTC)
    prior_status = _item_status_label(item)
    if is_correct:
        # MCQ recognition shouldn't single-shot promote to "mastered" —
        # only open-ended production (teach→use / use→define) mastery via
        # the background `master` action sets "mastered". MCQ correct on an
        # already-mastered word reinforces it (stays mastered). (LANG-TEACH-003)
        if prior_status == "mastered":
            new_status = "mastered"
        else:
            new_status = "learning"
    elif prior_status == "mastered":
        new_status = "learning"
    elif prior_status == "new":
        new_status = "learning"
    else:
        new_status = prior_status

    quality = quality_for_status(new_status, was_correct=is_correct)
    state = apply_sm2(
        quality=quality,
        ease_factor=float(getattr(item, "ease_factor", 2.5) or 2.5),
        interval_days=int(getattr(item, "interval_days", 0) or 0),
        review_count=int(item.review_count or 0),
        now=now,
    )
    return await learning_items_repo.apply_quiz_result(
        session,
        item,
        is_correct=is_correct,
        new_status=new_status,
        prior_status=prior_status,
        now=now,
        ease_factor=state.ease_factor,
        interval_days=state.interval_days,
        review_count=state.review_count,
        due_at=state.due_at,
        commit=commit,
    )


def _missed_on_local_today(item: LearningItem, *, timezone_name: str) -> bool:
    """True when last_incorrect_at is on the user's local calendar day.

    Same midnight as ``count_today_vocab_stats`` — not UTC date.
    """
    from app.services.daily_learning import start_of_today_utc

    missed = getattr(item, "last_incorrect_at", None)
    if not isinstance(missed, datetime):
        return False
    missed_utc = missed.astimezone(UTC) if missed.tzinfo else missed.replace(tzinfo=UTC)
    return missed_utc >= start_of_today_utc(timezone_name)


def _recently_missed_quiz(item: LearningItem, *, timezone_name: str = "UTC") -> bool:
    """Block sync-master after a fail on the user's local today."""
    return _missed_on_local_today(item, timezone_name=timezone_name)


def _failed_quiz_today(item: LearningItem, *, timezone_name: str = "UTC") -> bool:
    """True when last_incorrect_at is already on today's local calendar day."""
    return _missed_on_local_today(item, timezone_name=timezone_name)
