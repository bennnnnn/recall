"""A model's own answer line as a card draws it: no markdown marks, words kept as text."""

from __future__ import annotations

import pytest

from app.services.answer_fence import land_answer_card
from app.services.card_text import named_value, without_emphasis
from app.services.part_answer_cards import answers_by_letter, land_part_answer_cards


@pytest.mark.parametrize(
    ("written", "plain"),
    [
        ("(a) Work input = **1.2J**", "(a) Work input = 1.2J"),
        ("**$x = 3$**", "$x = 3$"),
        ("$x = **3**$", "$x = 3$"),
        ("__Speed__ = *20* m/s", "Speed = 20 m/s"),
        # A product or a subscript is no emphasis.
        ("a_b and x*y", "a_b and x*y"),
        ("$a_1 * b_2$", "$a_1 * b_2$"),
    ],
)
def test_without_emphasis_drops_markdown_marks(written: str, plain: str) -> None:
    assert without_emphasis(written) == plain


@pytest.mark.parametrize(
    ("value", "card"),
    [
        ("Work input = 1.2J", "Work input = $1.2\\,\\mathrm{J}$"),
        ("Efficiency = 100%", "Efficiency = $100\\,\\%$"),
        ("Final temperature = 25 °C", "Final temperature = $25\\,^\\circ\\mathrm{C}$"),
        (
            "Particles = 4.5 × 10^23 molecules",
            "Particles = $4.5 \\times 10^{23}\\,\\mathrm{molecules}$",
        ),
        # Maths, a bare symbol or a value that is no number stays as written.
        ("$x = 3$", "$x = 3$"),
        ("x = 3", "x = 3"),
        ("Capital = Paris", "Capital = Paris"),
    ],
)
def test_a_value_named_in_words_keeps_its_words_as_text(value: str, card: str) -> None:
    assert named_value(value) == card


_LEVER = (
    "**Given**  \nEffort = 40 N\n\n**Answer**\n- (a) Work input = **1.2J**\n"
    "- (b) Work output = 1.2 J\n- (c) Efficiency = 100%\n\nThe lever is ideal."
)


def test_lettered_answers_under_one_heading_each_get_their_own_card() -> None:
    """Live, 2026-11-03: only (a) went in the card, with its asterisks, and (b) and (c) stayed
    bullets under it."""
    out = land_part_answer_cards(_LEVER)
    assert out is not None
    for letter, value in (
        ("a", "Work input = $1.2\\,\\mathrm{J}$"),
        ("b", "Work output = $1.2\\,\\mathrm{J}$"),
        ("c", "Efficiency = $100\\,\\%$"),
    ):
        assert f"**Answer ({letter})**\n\n```answer\nverified: false\n{value}\n```" in out
    assert "**" not in out.split("```answer")[1].split("```")[0]
    assert out.rstrip().endswith("The lever is ideal.")


@pytest.mark.parametrize(
    "reply",
    [
        # One lettered line, letters out of order, or a sentence after (a): no parts.
        "**Answer**\n(a) Work input = 1.2 J",
        "**Answer**\n(b) Work output = 1.2 J\n(a) Work input = 1.2 J",
        "**Answer**\n(a) Work input = 1.2 J\nBoth are the same.",
        "Steps (a) and (b) below.\n\n```\n**Answer**\n(a) x = 1\n(b) y = 2\n```",
    ],
)
def test_answers_by_letter_leaves_anything_else_alone(reply: str) -> None:
    assert answers_by_letter(reply) == reply


def test_a_single_card_loses_its_bold_too() -> None:
    out = land_answer_card("**Answer**\nWork input = **1.2 J**", None)
    assert out == "**Answer**\n\n```answer\nverified: false\nWork input = $1.2\\,\\mathrm{J}$\n```"
