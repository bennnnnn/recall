"""A worked answer's card keeps three figures, rounded once from the working's value.

phys30 (2026-11-16): "3.2 N (to 2 s.f.)" stood under working that reached 3.24 N, and
"29.008 N" on the next question. The working ends unrounded; the card rounds once.
"""

from __future__ import annotations

import pytest

from app.modules.chat.worked_figures import card_answer
from app.modules.chat.worked_solution import Answer, Part, Step


def _part(*lines: str) -> Part:
    return Part(working=tuple(Step(kind="substitution", tex=line) for line in lines))


@pytest.mark.parametrize(
    ("value", "note", "working", "card", "kept_note"),
    [
        # Rounded below the working: the card is the working's value to three figures.
        (
            "3.2",
            "to 2 s.f.",
            ("T = \\frac{0.3 \\times 9.8}{\\cos 25^\\circ}", "T = 3.2439\\,\\mathrm{N}"),
            "3.24",
            "",
        ),
        ("0.31", "", ("x = 0.31139 m",), "0.311", ""),
        # More figures than three: rounded once.
        ("29.008", "", ("N = 29.008\\,\\mathrm{N}",), "29.0", ""),
        ("5.488", "down", (), "5.49", "down"),
        # Exact with fewer figures, or three already: as written.
        (
            "4.8",
            "away from the wall",
            ("J = 4.8\\,\\mathrm{N\\cdot s}",),
            "4.8",
            "away from the wall",
        ),
        ("96", "", ("F = 96 N",), "96", ""),
        ("3.24", "", ("T = 3.2439 N",), "3.24", ""),
        # The working ends on another value: the card is the reply's own.
        ("7.5", "", ("v = 3.2439 m/s",), "7.5", ""),
    ],
)
def test_the_card_keeps_three_figures_from_the_working(
    value: str, note: str, working: tuple[str, ...], card: str, kept_note: str
) -> None:
    out = card_answer(Answer(symbol="T", value=value, unit="N", note=note), _part(*working))
    assert (out.value, out.note) == (card, kept_note)


@pytest.mark.parametrize("value", ["\\frac{1}{2}", "9.79 \\times 10^{5}", "x + 2"])
def test_a_card_that_is_no_plain_number_stays(value: str) -> None:
    answer = Answer(symbol="v", value=value, unit="m/s")
    assert card_answer(answer, _part("v = 9.7864 m/s")) == answer
