from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.daily_learning import count_today_vocab_stats, start_of_today_utc


def _item(
    *,
    status: str = "new",
    created_at: datetime,
    mastered_at: datetime | None = None,
    mastered: bool = False,
):
    return SimpleNamespace(
        status=status,
        mastered=mastered,
        created_at=created_at,
        mastered_at=mastered_at,
    )


def test_start_of_today_utc_uses_timezone():
    start = start_of_today_utc("UTC")
    now = datetime.now(UTC)
    assert start <= now
    assert (now - start).total_seconds() < 86400


def test_count_today_vocab_stats_mastered_and_pending():
    start = start_of_today_utc("UTC")
    items = [
        _item(
            status="mastered",
            mastered=True,
            created_at=start,
            mastered_at=start,
        ),
        _item(status="new", created_at=start),
        _item(
            status="learning",
            created_at=start,
        ),
        _item(
            status="mastered",
            mastered=True,
            created_at=start.replace(year=start.year - 1),
            mastered_at=start.replace(year=start.year - 1),
        ),
    ]
    mastered_today, pending_today = count_today_vocab_stats(items, timezone_name="UTC")
    assert mastered_today == 1
    assert pending_today == 2
