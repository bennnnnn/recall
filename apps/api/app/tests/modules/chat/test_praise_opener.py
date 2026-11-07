"""A reply opens on the answer, not on praise of the question."""

from __future__ import annotations

import pytest

from app.modules.chat.praise_opener import drop_praise_opener


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        # Live 2026-11-06.
        ("Great question — here's how the factoring works.", "Here's how the factoring works."),
        ("Good question. Here's the thinking behind it.", "Here's the thinking behind it."),
        ("That's a great question! The answer is 4.", "The answer is 4."),
        ("Good question, and it depends on the bank.", "And it depends on the bank."),
        ("Great question:\n\nThe x is 2.", "The x is 2."),
    ],
)
def test_praise_of_the_question_comes_off(reply: str, kept: str) -> None:
    assert drop_praise_opener(reply) == kept


@pytest.mark.parametrize(
    "reply",
    [
        "Great question!",
        "Good question to ask your doctor: whether it still hurts after a week.",
        "That's a good question for your doctor.",
        "A good question is open-ended.",
        "Great questions start with why.",
        "The answer is 4. Great question.",
    ],
)
def test_other_replies_stay(reply: str) -> None:
    assert drop_praise_opener(reply) == reply
