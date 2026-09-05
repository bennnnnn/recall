from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.chat.prompt_constants.routing import needs_rich_context
from app.services.learning.insights import enrich_learning_stats
from app.services.projects.stats import stats_from_items


@pytest.mark.parametrize(
    "question", ["Do I have any lessons?", "Did I skip my reviews?", "How is my lesson progress?"]
)
def test_ordinary_lesson_questions_load_saved_learning_context(question):
    assert needs_rich_context(question)


def test_mastered_words_with_due_reviews_are_counted():
    now = datetime.now(UTC)
    item = SimpleNamespace(
        status="mastered",
        mastered=True,
        created_at=now - timedelta(days=10),
        mastered_at=now - timedelta(days=9),
        last_reviewed_at=now - timedelta(days=3),
        last_incorrect_at=None,
        due_at=now - timedelta(days=1),
    )
    assert stats_from_items([item])["due_for_review"] == 1


def test_inactivity_uses_actual_practice_instead_of_first_mastery():
    now = datetime.now(UTC)
    stats = {"last_mastery_at": now - timedelta(days=10), "last_study_at": now}
    result = enrich_learning_stats(stats, project=SimpleNamespace(), items=[], timezone_name="UTC")
    assert result["days_inactive"] == 0
