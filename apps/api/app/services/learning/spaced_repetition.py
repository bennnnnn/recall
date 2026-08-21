"""SM-2 spaced repetition helpers for vocabulary items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class Sm2State:
    ease_factor: float
    interval_days: int
    due_at: datetime
    review_count: int


def apply_sm2(
    *,
    quality: int,
    ease_factor: float = 2.5,
    interval_days: int = 0,
    review_count: int = 0,
    now: datetime | None = None,
) -> Sm2State:
    """Update SM-2 schedule from a 0-5 quality score (5 = perfect recall)."""
    when = now or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    q = max(0, min(5, int(quality)))
    ef = max(1.3, float(ease_factor or 2.5))
    interval = max(0, int(interval_days or 0))
    reps = max(0, int(review_count or 0))

    if q < 3:
        reps = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ef))
        reps += 1

    # BUG FIX (was silent): the EF update used to live only in the q>=3 branch above,
    # so canonical SM-2's EF decrease on a failed review (q<3) never applied — EF only
    # ever moved upward. Apply it for every quality score, per the original algorithm.
    ef = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ef = max(1.3, ef)

    return Sm2State(
        ease_factor=round(ef, 4),
        interval_days=interval,
        due_at=when + timedelta(days=interval),
        review_count=reps,
    )


def quality_for_status(status: str, *, was_correct: bool | None = None) -> int:
    if was_correct is False:
        return 1
    if status == "mastered" or was_correct is True:
        return 5
    if status == "learning":
        return 3
    return 2
