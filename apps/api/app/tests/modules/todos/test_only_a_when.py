"""A message that only says when: it says nothing about the user, and after the To-do
button it asks for the same reminder again."""

from __future__ import annotations

import pytest

from app.modules.todos.spoken_when import half_of_day, is_only_a_when


@pytest.mark.parametrize(
    ("text", "half"),
    [("pm", 12), ("P.M.", 12), ("in the evening", 12), ("am", 0), ("morning", 0), ("6pm", None)],
)
def test_half_of_day_reads_a_reply_that_is_only_its_half(text: str, half: int | None) -> None:
    assert half_of_day(text) == half


@pytest.mark.parametrize(
    ("text", "only"),
    [
        ("6pm", True),
        ("tomorrow at 6", True),
        ("ok friday then", True),
        ("pm", True),
        ("in 20 minutes", True),
        ("I start work at 6pm", False),
        ("i wake up at 6 every day", False),
        ("I am 6 feet tall", False),
    ],
)
def test_is_only_a_when(text: str, only: bool) -> None:
    assert is_only_a_when(text) is only
