"""A physics question's graph, drawn as any curve is: held to the question's own formula."""

from __future__ import annotations

import pytest

from app.modules.math.drawing.plot_question import read_plot_question
from app.tests.modules.math.drawing.test_plot_review import _curve, _plot

_U5_087 = (
    "Find the work done when a particle is moved through a displacement of 10 m along a "
    "smooth horizontal surface by a force of magnitude F = (9 − x/2) N, where x is the "
    "displacement from its initial position in metres. Show the work as an area on the "
    "force–displacement graph."
)


@pytest.mark.parametrize(
    ("question", "expr"),
    [
        (_U5_087, "9 - x/2"),
        ("The velocity is v = (3t + 2) m/s for 0 ≤ t ≤ 4. Draw the v–t graph.", "3*t + 2"),
        ("The force is F = (2x + 1) kN. Draw it.", "2*x + 1"),
        ("The acceleration is a = (t^2 - 1) m/s². Sketch a against t.", "t**2 - 1"),
    ],
)
def test_a_formula_with_its_unit_after_a_bracket_is_read(question: str, expr: str) -> None:
    from sympy import sympify

    written = [w.expr for w in read_plot_question([question]).formulas if w.name in "Fva"]
    assert any((w - sympify(expr)).equals(0) for w in written)


@pytest.mark.parametrize("formula", ["(x + 1) k", "(x + 1) x"])
def test_a_letter_after_a_bracket_that_is_no_unit_stays(formula: str) -> None:
    from app.modules.math.drawing.plot_question import _without_unit

    assert _without_unit(formula) == formula


def test_a_force_displacement_graph_draws_the_question_s_force() -> None:
    graph = _plot(
        _U5_087,
        _curve("F", "9 - x/2", domain=["0", "10"]),
        reply="W = ∫₀¹⁰ (9 − x/2) dx = 65 J",
    )
    assert graph is not None and [curve.label for curve in graph.curves] == ["F = 9 − x/2"]


def test_a_force_the_question_does_not_write_is_not_drawn() -> None:
    assert _plot(_U5_087, _curve("F", "9 - x/3", domain=["0", "10"])) is None


@pytest.mark.parametrize(
    ("question", "y", "drawn"),
    [
        # A letter the question gives a value is a factor, never a unit.
        ("Sketch y = (x + 1) m, where m = 3.", "x + 1", False),
        # A unit after the formula's own variable.
        ("The position of a particle is x = t^2 - 4t m. Sketch x against t.", "t^2 - 4t", True),
        # The formula ends where prose begins.
        ("A force F = (9 - x/2) N moves a body through a displacement of 10 m, where x is the "
         "displacement. Sketch F against x.", "9 - x/2", True),
        ("A particle has velocity v = (4 - t) m s. Sketch v.", "4 - t", True),
    ],
)  # fmt: skip
def test_a_unit_is_read_only_where_it_is_one(question: str, y: str, drawn: bool) -> None:
    assert (_plot(question, _curve("f", y)) is not None) is drawn


@pytest.mark.parametrize("formula", ["2 pi", "(x + 1) pi", "2 sin s", "3 cos t"])
def test_a_constant_or_a_function_s_argument_is_no_unit(formula: str) -> None:
    from app.modules.math.drawing.plot_question import _without_unit

    assert _without_unit(formula) == formula
