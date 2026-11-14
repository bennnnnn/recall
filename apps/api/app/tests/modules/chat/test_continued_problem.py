"""The pieces of a problem a model named (``turn_reading.continued_problem``): a number
completes a list left open, a quantity asked of it is its question."""

from __future__ import annotations

import pytest

from app.modules.turn_reading.continued_problem import (
    Problem,
    adds_to_problem,
    continue_problem,
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
    ("problem", "line", "joined"),
    [
        (Problem("Triangle are with sides 5, 4,"), "3", "Triangle are with sides 5, 4, 3"),
        (Problem("a rectangle 3 by 5"), "the area", "a rectangle 3 by 5. the area"),
        (
            Problem("a rectangle 3 by 5", "the area"),
            "and its perimeter?",
            "a rectangle 3 by 5. and its perimeter?",
        ),
        # A number with no list left open is no piece of it; nor is a line of its own.
        (Problem("Solve 2x + 3 = 7"), "3", None),
        (Problem("a rectangle 3 by 5"), "draw it", None),
    ],
)
def test_a_line_is_added_to_a_problem_by_its_shape(
    problem: Problem, line: str, joined: str | None
) -> None:
    continued = continue_problem(problem, line)
    assert (continued.text if continued is not None else None) == joined


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
