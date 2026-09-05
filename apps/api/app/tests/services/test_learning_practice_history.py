from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.config import Settings
from app.models.orm import LearningPracticeEvent, Project
from app.models.schemas import ProjectStats
from app.services.home.project_starters import completed_today, project_highlight
from app.services.learning.insights import pick_learning_nudge
from app.services.learning.practice_context import load_activity_context
from app.services.learning.practice_history import merge_practice_history, merge_practice_items
from app.services.projects.prompt_context import load_projects_for_prompt

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)
YESTERDAY = NOW - timedelta(days=1)


def item(**kw):
    values = dict(
        id=uuid4(),
        project_id=uuid4(),
        status="new",
        mastered=False,
        mastered_at=None,
        last_completed_at=None,
        last_incorrect_at=None,
        last_reviewed_at=None,
        created_at=NOW - timedelta(days=10),
        due_at=None,
        content="hello",
        quiz_attempts=0,
        quiz_correct=0,
    )
    return SimpleNamespace(**(values | kw))


def event(word, *, correct=True, complete=False, when=YESTERDAY):
    return LearningPracticeEvent(
        id=uuid4(),
        attempt_id=uuid4(),
        item_id=word.id,
        project_id=word.project_id,
        user_id=uuid4(),
        was_correct=correct,
        completes_word=complete,
        occurred_at=when,
    )


def history(*, missed=0):
    return [
        dict(
            date="2026-09-05",
            mastered_count=0,
            missed_count=missed,
            daily_goal=2,
            goal_met=False,
            status="partial" if missed else "skipped",
        )
    ]


def test_partial_and_wrong_only_practice_are_activity_not_completion_or_skipping():
    for correct in (True, False):
        word = item(last_incorrect_at=YESTERDAY if not correct else None)
        rows = merge_practice_history(
            history(missed=int(not correct)),
            [word],
            [event(word, correct=correct)],
            timezone_name="UTC",
            now=NOW,
        )
        assert rows[0]["completed_count"] == 0
        assert rows[0]["attempted_count"] == 1
        assert rows[0]["status"] == "partial"
        assert rows[0]["goal_met"] is False


def test_review_counts_once_per_day_without_moving_first_mastery():
    first_mastery = NOW - timedelta(days=8)
    word = item(status="mastered", mastered=True, mastered_at=first_mastery)
    events = [event(word), event(word, complete=True), event(word, complete=True)]
    rows = merge_practice_history(history(), [word], events, timezone_name="UTC", now=NOW)
    assert rows[0]["mastered_count"] == 0
    assert rows[0]["completed_count"] == rows[0]["attempted_count"] == 1
    assert word.mastered_at == first_mastery
    groups = merge_practice_items(
        {"2026-09-05": []}, [word], events, timezone_name="UTC", allowed_days={"2026-09-05"}
    )
    assert groups == {"2026-09-05": [word]}


def test_mixed_legacy_history_keeps_earlier_miss_after_later_mastery():
    reviewed, legacy = item(), item(status="mastered", mastered=True, mastered_at=NOW)
    rows = merge_practice_history(
        history(missed=1),
        [reviewed, legacy],
        [event(reviewed)],
        timezone_name="UTC",
        now=NOW,
        miss_events_by_item={legacy.id: [YESTERDAY]},
    )
    assert rows[0]["completed_count"] == 1
    assert rows[0]["attempted_count"] == 2
    assert rows[0]["missed_count"] == 1


def test_old_history_is_retained_without_new_events_and_timezone_is_applied():
    rows = merge_practice_history(history(missed=1), [], [], timezone_name="UTC", now=NOW)
    assert rows[0]["completed_count"] == rows[0]["attempted_count"] == 1
    word = item()
    rows = merge_practice_history(
        history(),
        [word],
        [event(word, when=NOW.replace(hour=2))],
        timezone_name="America/Los_Angeles",
        now=NOW,
    )
    assert rows[0]["status"] == "partial"
    assert rows[0]["attempted_count"] == 1


def test_home_partial_practice_does_not_complete_goal_or_claim_inactivity():
    now = datetime.now(UTC)
    stats = ProjectStats(
        total=10,
        mastered_today=0,
        missed_today=1,
        completed_today=0,
        attempted_today=1,
        last_study_at=now,
        last_mastery_at=now - timedelta(days=5),
    )
    project = Project(id=uuid4(), title="English", kind="language", daily_goal=1, created_at=now)
    highlight = project_highlight(project, stats, home_tz=ZoneInfo("UTC"))
    assert completed_today(stats) == 0
    assert highlight.cue == "continue"
    assert highlight.days_inactive == 0
    assert highlight.completed_today == 0 and highlight.attempted_today == 1


def test_nudge_uses_partial_activity_and_due_mastered_reviews():
    project = Project(id=uuid4(), title="English", kind="language")
    base = dict(
        total=10,
        completed_today=0,
        attempted_today=1,
        mastered_today=0,
        missed_today=1,
        days_inactive=0,
        new_count=9,
        learning_count=1,
        due_for_review=0,
    )
    body, _, kind, _ = pick_learning_nudge(project, base, daily_goal=1)
    assert kind == "learning_daily_goal" and "0/1 done" in body and "1 word practiced" in body
    review_stats = base | dict(new_count=0, learning_count=0, due_for_review=2)
    assert pick_learning_nudge(project, review_stats, daily_goal=1)[2] == "learning_review"
    assert (
        pick_learning_nudge(project, review_stats | dict(completed_today=1), daily_goal=1) is None
    )
    assert pick_learning_nudge(project, review_stats | dict(due_for_review=0), daily_goal=1) is None


@pytest.mark.asyncio
async def test_no_active_class_is_explicit_in_ordinary_chat_context():
    with patch("app.repositories.projects.list_for_user", AsyncMock(return_value=[])):
        result = await load_projects_for_prompt(AsyncMock(), uuid4(), Settings())
    assert "no active Learning class" in result


@pytest.mark.asyncio
async def test_chat_uses_saved_partial_activity_for_skipped_days():
    now = datetime.now(UTC)
    project = Project(
        id=uuid4(),
        title="English",
        kind="language",
        daily_goal=5,
        created_at=now - timedelta(days=7),
    )
    word = item(project_id=project.id, last_reviewed_at=now - timedelta(days=1))
    saved = event(word, when=word.last_reviewed_at)
    with (
        patch("app.repositories.learning_practice.list_events", AsyncMock(return_value=[saved])),
        patch(
            "app.repositories.project_items.list_miss_events_for_items", AsyncMock(return_value={})
        ),
    ):
        text = await load_activity_context(AsyncMock(), [project], [word], timezone_name="UTC")
    skipped = next(line for line in text.splitlines() if "no recorded practice:" in line)
    assert word.last_reviewed_at.date().isoformat() not in skipped
    assert "Last recorded study:" in text
    assert "Do not invent" in text


def test_same_day_first_mastery_remains_completed_during_partial_review():
    word = item(status="mastered", mastered=True, mastered_at=YESTERDAY.replace(hour=9))
    rows = history()
    rows[0]["mastered_count"] = 1
    merged = merge_practice_history(
        rows, [word], [event(word, when=YESTERDAY.replace(hour=10))], timezone_name="UTC", now=NOW
    )
    assert merged[0]["completed_count"] == merged[0]["attempted_count"] == 1
    assert merged[0]["mastered_count"] == 1
