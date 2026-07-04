import pytest

from app.services.day_planning import (
    is_day_planning_question,
    is_day_reflection_question,
    needs_gmail_for_day_planning,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "How's my day looking so far — anything you think I should prioritize?",
            True,
        ),
        ("Help me plan my day based on what you know about me.", True),
        ("What should I focus on today?", True),
        ("How did my day go? Help me reflect and wrap up loose ends.", True),
        ("What's still open for me to finish tonight?", True),
        ("What's on my calendar today?", False),
        ("check my email", False),
        ("Tell me a joke", False),
    ],
)
def test_is_day_planning_question(text, expected):
    assert is_day_planning_question(text) is expected


def test_reflection_skips_gmail_but_still_day_planning():
    text = "How did my day go? Help me reflect and wrap up loose ends."
    assert is_day_planning_question(text)
    assert is_day_reflection_question(text)
    assert not needs_gmail_for_day_planning(text)


def test_morning_planning_still_wants_gmail():
    text = "How's my day looking so far — anything you think I should prioritize?"
    assert is_day_planning_question(text)
    assert not is_day_reflection_question(text)
    assert needs_gmail_for_day_planning(text)
