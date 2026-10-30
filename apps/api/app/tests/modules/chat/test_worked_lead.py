"""A worked reply's result comes after its working, never as a guess above it (2026-10-30)."""

from __future__ import annotations

import pytest

from app.modules.chat.worked_lead import drop_guessed_lead

_WORKED = (
    "**Given**\n$m_1 = 160\\ \\text{kg}$\n\n**Formula**\n$E = \\frac{1}{2}Mv^2$\n\n"
    "**Answer**\n\n```answer\n$E_1 : E_2 = 4 : 5$\n```\n"
)


@pytest.mark.parametrize(
    "lead",
    [
        "The ratio of fuel used on the first day to the second day is **5: 7**\n\n",
        "The car covers **290 m** in total.\n\n",
        "The time of contact is **0.054 s**.\n\n",
    ],
)
def test_a_number_above_the_working_goes(lead: str) -> None:
    assert drop_guessed_lead(lead + _WORKED) == _WORKED


def test_a_heading_or_a_photo_above_the_working_stays() -> None:
    text = "[Image: /attachments/a1b2/file]\n\n## Stage 1\n\nAtomic structure of Mg\n\n" + _WORKED
    assert drop_guessed_lead(text) == text


def test_only_the_guess_goes_from_a_lead_with_a_heading() -> None:
    text = "## Stage 1\n\nThe car covers **290 m**.\n\n" + _WORKED
    assert drop_guessed_lead(text) == "## Stage 1\n\n" + _WORKED


@pytest.mark.parametrize(
    "text",
    [
        # No card: the lead may be the only place the answer is.
        "The car covers **310 m**.\n\n**Given**\n$u = 0$\n",
        # A long lead is an answer of its own, not a guess.
        " ".join(["word"] * 70) + " 12 m\n\n" + _WORKED,
        # A Given in a code example is not the reply's working.
        "Use 3 workers.\n\n```md\n**Given**\n```\n\n```answer\n3\n```\n",
        # No number above the working.
        "Here is the working.\n\n" + _WORKED,
    ],
)
def test_anything_else_is_left_alone(text: str) -> None:
    assert drop_guessed_lead(text) == text


def test_a_photo_fence_above_the_working_stays() -> None:
    text = "```photo\nEiffel Tower 1889\n```\n\n" + _WORKED
    assert drop_guessed_lead(text) == text
