"""A physics question's graph, drawn as any curve is: held to the question's own formula."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.math.drawing.plot_question import read_plot_question
from app.tests.modules.math.drawing.test_plot_review import _curve, _plot, _shade

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


_U5_088 = (
    "A particle P moves along a straight line OX with acceleration 3.5t m/s². When t = 2 s, "
    "P is 10 m from O and has velocity 15 m/s. Find the velocity and the displacement when "
    "t = 5 s. Draw the velocity–time graph and show the distance covered between t = 2 and "
    "t = 5 as an area."
)
_U5_089 = (
    "A particle P starts from a point A with velocity 4 m/s. It moves along a straight line AB "
    "with an acceleration of −1.5t² m/s² at time t seconds. Find (a) the acceleration (b) the "
    "velocity and (c) the displacement after ten seconds, and the total distance travelled in "
    "that time. Draw the velocity–time graph and show the displacement and the distance on it."
)


@pytest.mark.parametrize(
    ("question", "formulas"),
    [
        (_U5_088, {"a": "7*t/2", "v": "7*t**2/4 + 8", "s": "7*t**3/12 + 8*t - 32/3"}),
        (_U5_089, {"a": "-3*t**2/2", "v": "4 - t**3/2", "s": "4*t - t**4/8"}),
        # From rest at the start: v(0) = 0; no position stated, no displacement.
        ("A body moves from rest with acceleration (6t - 2) m/s². Draw its v-t graph.",
         {"a": "6*t - 2", "v": "3*t**2 - 2*t"}),
        # No velocity stated: only the acceleration.
        ("A particle moves with acceleration 2t m/s². Sketch a against t.", {"a": "2*t"}),
    ],
)  # fmt: skip
def test_the_motion_is_worked_out_from_the_values_it_states(
    question: str, formulas: dict[str, str]
) -> None:
    from sympy import sympify

    from app.modules.math.drawing.plot_motion import motion_formulas
    from app.modules.math.drawing.plot_reading import plain

    found = {name: expr for name, expr, _unit in motion_formulas(plain(question))}
    assert set(found) == set(formulas)
    assert all((found[n] - sympify(e, locals={"t": _t()})).equals(0) for n, e in formulas.items())


def _t() -> Any:
    from sympy import Symbol

    return Symbol("t")


@pytest.mark.parametrize(
    ("question", "curve", "shades", "spans"),
    [
        (_U5_088, _curve("v", "1.75t^2 + 8", domain=["0", "5"]),
         [_shade("v", "x-axis", "2", "5")], [(2.0, 5.0)]),
        (_U5_089, _curve("v", "4 - 0.5t^3", domain=["0", "10"]),
         [_shade("v", "x-axis", "0", "2"), _shade("v", "x-axis", "2", "10")],
         [(0.0, 2.0), (2.0, 10.0)]),
    ],
)  # fmt: skip
def test_a_velocity_time_graph_worked_out_from_the_question_is_drawn(
    question: str,
    curve: dict[str, Any],
    shades: list[dict[str, Any]],
    spans: list[tuple[float, float]],
) -> None:
    graph = _plot(question, curve, *shades)
    assert graph is not None and graph.curves[0].label.startswith("v = ")
    drawn = sorted(
        (round(min(x for x, _ in r.points), 6), round(max(x for x, _ in r.points), 6))
        for r in graph.regions
    )
    assert drawn == spans


@pytest.mark.parametrize(
    "y",
    [
        "1.75t^2 + 9",  # the wrong constant: v(2) is no 15
        "1.75t^2",  # no constant at all
        "3.5t^2 + 1",  # integrated wrong
    ],
)
def test_a_velocity_the_stated_values_do_not_give_is_not_drawn(y: str) -> None:
    assert _plot(_U5_088, _curve("v", y)) is None


def test_a_force_moved_through_a_displacement_shades_the_work() -> None:
    graph = _plot(
        _U5_087,
        _curve("F", "9 - x/2", domain=["0", "10"]),
        _shade("F", "x-axis", "0", "10"),
        {"item": "axes", "x": "x (m)", "y": "F (N)"},
    )
    assert graph is not None and len(graph.regions) == 1
    assert (graph.x_label, graph.y_label) == ("x (m)", "F (N)")


def test_a_velocity_described_in_x_is_the_question_s_v_of_t() -> None:
    # u5-088 live: the reply wrote 1.75x² + 8 for v(t), the graph's across as x.
    graph = _plot(_U5_088, _curve("v", "1.75*x^2 + 8"))
    assert graph is not None and [c.label for c in graph.curves] == ["v = 7t²/4 + 8"]
    assert _plot(_U5_088, _curve("v", "1.75*x^2 + 9")) is None
