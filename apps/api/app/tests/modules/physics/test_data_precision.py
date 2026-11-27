"""The data's significant figures are the values the solver read, as the question wrote them,
never any number the text holds (review of #2604: a list's "1." showed a checked 3.62 m/s as
"4 m/s")."""

from __future__ import annotations

import pytest

from app.modules.physics.data_precision import bound_figures
from app.modules.physics.extract import extract_physics_intent

_ASKED = "Give the answer to the correct number of significant figures."
_TROLLEY = f"A trolley travels 4.345 m in 1.20 s. What is its average speed? {_ASKED}"


@pytest.mark.parametrize(
    "written",
    [
        # The reviewer's input, and the same values with other numbers that are no data.
        f"1. {_TROLLEY}",
        f"Question 2: {_TROLLEY}",
        f"Exercise 4.3 {_TROLLEY}",
        f"Q7) {_TROLLEY}",
        f"{_TROLLEY} (Use v = 1/2 (u + v) only if it helps.)",
        f"Part 3 of 5: {_TROLLEY}",
    ],
)
def test_only_the_values_the_solver_read_count(written: str) -> None:
    intent = extract_physics_intent(_TROLLEY)
    assert intent is not None
    assert bound_figures(intent, written) == 3  # 4.345 m (4) and 1.20 s (3)


@pytest.mark.parametrize(
    ("question", "figures"),
    [
        (_TROLLEY, 3),
        (
            "A trolley travels a distance of 4.345 m in a time of 1.2 s. What is its average "
            f"speed? {_ASKED}",
            2,
        ),
        (
            "In 1.2 s a trolley covers 4.345 m. Using the right number of significant figures, "
            "what is its speed?",
            2,
        ),
        (
            "A TROLLEY TRAVELS 4.345 m IN 1.2 s. WHAT IS ITS AVERAGE SPEED, TO THE CORRECT NUMBER "
            "OF SIGNIFICANT FIGURES?",
            2,
        ),
    ],
)
def test_a_solved_question_gives_its_data_s_figures(question: str, figures: int) -> None:
    assert bound_figures(extract_physics_intent(question), question) == figures


def test_no_solve_no_data_figures() -> None:
    assert bound_figures(None, _TROLLEY) == 0


_FIGURES = " Give the answer to the correct number of significant figures."


@pytest.mark.parametrize(
    "question",
    [
        # The reviewer's input (round 2 of #2604): the solve stores a = -2.0, the scan +2.0.
        "A car at 25.0 m/s decelerates at 2.0 m/s² for 4.00 s. What is its final speed?",
        "A car moving at 25.0 m/s slows down at 2.0 m/s² for 4.00 s. Find its final speed.",
        "A train at 25.0 m/s has an acceleration of -2.0 m/s² for 4.00 s. What is its final "
        "velocity?",
        "A cyclist going 25.0 m/s brakes with a deceleration of 2.0 m/s² for 4.00 s. How fast "
        "is she going then?",
    ],
)
def test_a_value_stored_with_its_direction_s_sign_still_counts(question: str) -> None:
    question += _FIGURES
    assert bound_figures(extract_physics_intent(question), question) == 2  # 2.0 m/s²
