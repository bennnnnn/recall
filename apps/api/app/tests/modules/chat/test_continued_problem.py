"""A line that adds to the open problem (``turn_reading.continued_problem``), by the shape of
the exchange before it: a number answers a question the reply asked, a quantity asks anew
after a reply that asked nothing."""

from __future__ import annotations

import pytest

from app.modules.turn_reading.continued_problem import (
    Problem,
    adds_to_problem,
    continued_problem_text,
    problem_at,
)

_PIECES = [
    ("user", "Differentiate sin(x^2)cos(x^2)"),
    ("assistant", "2x cos(2x^2)"),
    ("user", "Triangle are with sides 5, 4,"),
    ("assistant", "What's the third side length? 🔺"),
    ("user", "3"),
    ("assistant", "Sides 3, 4 and 5 make a right triangle."),
    ("user", "The area"),
    ("assistant", "6 square units."),
    ("user", "Do it properly"),
    ("assistant", "Area = 6."),
]


@pytest.mark.parametrize("index", [2, 4, 6])
def test_any_piece_of_a_problem_is_the_problem_whole(index: int) -> None:
    """Whichever line a model picks as "it", the triangle is 5, 4 and 3."""
    assert problem_at(_PIECES, index) == Problem("Triangle are with sides 5, 4, 3", "The area")


def test_a_line_of_its_own_is_its_own_problem() -> None:
    assert problem_at(_PIECES, 0) == Problem("Differentiate sin(x^2)cos(x^2)")
    assert problem_at(_PIECES, 8) == Problem("Do it properly")


@pytest.mark.parametrize(
    ("line", "earlier", "joined"),
    [
        ("3", _PIECES[2:4], "Triangle are with sides 5, 4, 3"),
        # A question asked anywhere in the reply's last paragraph (a live reply, 2026-11-10).
        (
            "3",
            [
                ("user", "Triangle are with sides 5, 4,"),
                ("assistant", "Did you mean the third side? Send it and I'll work it out."),
            ],
            "Triangle are with sides 5, 4, 3",
        ),
        ("The area", _PIECES[2:6], "Triangle are with sides 5, 4, 3. The area"),
        # A question asked last: the line answers it, it adds nothing.
        (
            "the hypotenuse",
            [("user", "legs 3 and 4"), ("assistant", "Which side is longest?")],
            None,
        ),
        # A number with no question before it, or no list left open.
        ("3", [("user", "Triangle are with sides 5, 4,"), ("assistant", "A triangle.")], None),
        ("3", [("user", "Solve 2x + 3 = 7"), ("assistant", "Which method?")], None),
    ],
)
def test_a_line_joins_only_by_the_exchange_before_it(
    line: str, earlier: list[tuple[str, str]], joined: str | None
) -> None:
    assert continued_problem_text(line, earlier) == joined


@pytest.mark.parametrize(
    ("line", "adds"),
    [
        ("3", True),
        ("$5$", True),
        ("The area", True),
        ("and its perimeter?", True),
        ("draw it", False),
        ("Do it properly", False),
        ("x", False),
        ("thanks", False),
        ("площадь", False),
    ],
)
def test_a_number_or_a_quantity_adds_to_a_problem(line: str, adds: bool) -> None:
    assert adds_to_problem(line) is adds
