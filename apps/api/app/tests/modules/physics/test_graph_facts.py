"""Physics' reading of a question's words for maths' plot: a particle's motion as formulas
(``physics.graph_facts``), and the graphs a reply describes held to them."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.math.drawing.build import drawn_fence
from app.modules.math.drawing.plot_reading import plain
from app.modules.math.schemas.plot import PlotGraphSpec
from app.modules.physics.graph_facts import motion_formulas, read_graph_facts
from app.tests.modules.math.drawing.test_plot_review import _curve, _shade

_U5_087 = (
    "Find the work done when a particle is moved through a displacement of 10 m along a "
    "smooth horizontal surface by a force of magnitude F = (9 − x/2) N, where x is the "
    "displacement from its initial position in metres. Show the work as an area on the "
    "force–displacement graph."
)


def _plot(question: str, *items: dict[str, Any], reply: str = "") -> PlotGraphSpec | None:
    import json

    body = json.dumps({"kind": "plot", "items": list(items)})
    fence = drawn_fence(body, [question], reply, read_graph_facts)
    if fence is None:
        return None
    return PlotGraphSpec.model_validate_json(fence.split("\n", 1)[1].rsplit("\n```", 1)[0])


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
        # "10 m from O" says no side of O: no displacement (PR #2486 review).
        (_U5_088, {"a": "7*t/2", "v": "7*t**2/4 + 8"}),
        (_U5_089, {"a": "-3*t**2/2", "v": "4 - t**3/2", "s": "4*t - t**4/8"}),
        # From rest at the start: v(0) = 0; where it starts is not said, so no displacement.
        ("A body moves from rest with acceleration (6t - 2) m/s². Draw its v-t graph.",
         {"a": "6*t - 2", "v": "3*t**2 - 2*t"}),
        # ... measured from where it starts when the question names the place.
        ("A body moves from rest at O with acceleration (6t - 2) m/s². Draw its graphs.",
         {"a": "6*t - 2", "v": "3*t**2 - 2*t", "s": "t**3 - t**2"}),
        # No velocity stated: only the acceleration.
        ("A particle moves with acceleration 2t m/s². Sketch a against t.", {"a": "2*t"}),
    ],
)  # fmt: skip
def test_the_motion_is_worked_out_from_the_values_it_states(
    question: str, formulas: dict[str, str]
) -> None:
    from sympy import sympify

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


@pytest.mark.parametrize(
    ("question", "formulas"),
    [
        # Each value at the time its own clause names, in either order.
        ("A particle moves with acceleration 6t m/s². When t = 1 s it has velocity 4 m/s, and "
         "when t = 3 s it is 20 m to the right of O. Sketch s.",
         {"a": "6*t", "v": "3*t**2 + 1", "s": "t**3 + t - 10"}),
        ("A particle moves with acceleration 6t m/s². It is 20 m to the right of O when t = 3 s, "
         "and its velocity is 4 m/s when t = 1 s. Sketch s.",
         {"a": "6*t", "v": "3*t**2 + 1", "s": "t**3 + t - 10"}),
        # At rest at the start and 10 m/s after 4 s: no v(t) = t² + C holds both.
        ("Initially at rest, after 4 s a particle has velocity 10 m/s. It moves with "
         "acceleration 2t m/s². Sketch v.", {"a": "2*t"}),
        # From rest is no place it starts from: s(2) = 10 alone fixes s.
        ("A particle starts from rest. Its acceleration is 6t m/s². When t = 2 s it is 10 m "
         "to the right of O. Sketch s.", {"a": "6*t", "v": "3*t**2", "s": "t**3 + 2"}),
        ("A particle's acceleration is 4t m/s². At t = 0 its velocity is 3 m/s and its "
         "displacement is 5 m.", {"a": "4*t", "v": "2*t**2 + 3", "s": "2*t**3/3 + 3*t + 5"}),
        # "is", and the units m s^-2, ms^-2 and ms^-1.
        ("The acceleration is 2t m s^-2. When t = 0 it has velocity 1 m/s.",
         {"a": "2*t", "v": "t**2 + 1"}),
        ("A particle moves with acceleration 6t ms^-2. When t = 0 it has velocity 1 ms^-1.",
         {"a": "6*t", "v": "3*t**2 + 1"}),
        # A constant acceleration, said at no one time.
        ("A car starts from rest with acceleration 2 m/s². Draw the v-t graph for 5 s.",
         {"a": "2", "v": "2*t"}),
        ("A car starts from rest with acceleration 2 m/s². Sketch its displacement from its "
         "starting point for 5 s.", {"a": "2", "v": "2*t", "s": "t**2"}),
        # A velocity the question writes, held to what it states (PR #2486 review).
        ("At t = 2 s a particle is at rest, and later moves with velocity 2t m/s. Sketch s.", {}),
        ("A particle moves with velocity 2t m/s and acceleration 3 m/s². Sketch v.", {}),
        ("A particle moves with velocity (2t + 1) m/s and acceleration 2 m/s². It starts from "
         "O. Sketch s.", {"a": "2", "v": "2*t + 1", "s": "t**2 + t"}),
        ("When t = 2 s its acceleration is 3 m/s² and its velocity is 4 m/s. Sketch v.", {}),
    ],
)  # fmt: skip
def test_each_value_is_said_at_its_own_time(question: str, formulas: dict[str, str]) -> None:
    test_the_motion_is_worked_out_from_the_values_it_states(question, formulas)


@pytest.mark.parametrize(
    ("question", "s"),
    [
        ("A particle moves with velocity 2t m/s. When t = 1 s it is 3 m from O. Sketch s.", None),
        ("A particle moves with velocity 2t m/s. When t = 1 s it is 3 m to the left of O.",
         "t**2 - 4"),
        ("A particle moves with velocity 2t m/s. When t = 1 s it is 3 m from O on the positive "
         "side of O.", "t**2 + 2"),
        ("A particle moves with velocity 2t m/s. When t = 1 s, s = -3 m.", "t**2 - 4"),
        # The origin tied to the start: "at O" at t = 2 is no start.
        ("A particle starts from rest with acceleration 2 m/s². When t = 2 s it is at O.", None),
        ("A particle starts from rest at O with acceleration 2 m/s².", "t**2"),
    ],
)  # fmt: skip
def test_a_position_is_bound_only_where_its_sign_is_said(question: str, s: str | None) -> None:
    from sympy import sympify

    found = {name: expr for name, expr, _unit in motion_formulas(plain(question))}
    if s is None:
        assert "s" not in found
    else:
        assert (found["s"] - sympify(s, locals={"t": _t()})).equals(0)


@pytest.mark.parametrize(
    ("question", "formulas"),
    [
        # "Initial" is t = 0; the asked clause lends no time (PR #2486 review).
        ("A particle with initial velocity 4 m/s moves with acceleration 2t m/s², find its "
         "velocity when t = 3 s and draw the v–t graph.", {"a": "2*t", "v": "t**2 + 4"}),
        # A start some distance from O fixes no s(0) = 0; "a" is no point.
        ("A particle starts from rest 10 m from O with acceleration 2 m/s². Sketch s.",
         {"a": "2", "v": "2*t"}),
        ("A particle starts from rest at a corner with acceleration 2 m/s². Sketch s.",
         {"a": "2", "v": "2*t"}),
        ("A particle starts from rest at O with acceleration 2 m/s². Sketch s.",
         {"a": "2", "v": "2*t", "s": "t**2"}),
    ],
)  # fmt: skip
def test_review_round_two_cases(question: str, formulas: dict[str, str]) -> None:
    test_the_motion_is_worked_out_from_the_values_it_states(question, formulas)


def test_a_region_where_the_velocity_is_negative_stands_inside_the_motion() -> None:
    # The motion's [0, 5] grounds the curve but ties no region: [1, 3] is drawn.
    question = (
        "A particle has velocity 3 m/s at t = 0 and acceleration (2t - 4) m/s² for 5 s. Draw "
        "the v-t graph and shade the region where the velocity is negative."
    )
    graph = _plot(question, _curve("v", "t^2 - 4t + 3"), _shade("v", "x-axis", "1", "3"))
    assert graph is not None and len(graph.regions) == 1


@pytest.mark.parametrize(
    ("question", "formulas"),
    [
        # A value at one instant is no a(t) = c (PR #2486 review).
        ("Initially its acceleration is 3 m/s² and its velocity is 4 m/s. Sketch v against t.", {}),
        ("When at rest, its acceleration is 2 m/s². Sketch v.", {}),
        # ... unless said to be held.
        ("Its acceleration is a constant 3 m/s² and initially its velocity is 4 m/s. Sketch v.",
         {"a": "3", "v": "3*t + 4"}),
        ("A particle with initial velocity 4 m/s moves with acceleration 2 m/s². Sketch v.",
         {"a": "2", "v": "2*t + 4"}),
    ],
)  # fmt: skip
def test_an_acceleration_at_an_instant_is_no_constant_one(
    question: str, formulas: dict[str, str]
) -> None:
    test_the_motion_is_worked_out_from_the_values_it_states(question, formulas)


def test_a_follow_up_draws_with_the_question_s_motion() -> None:
    import json

    from app.modules.math.drawing.build import drawn_fences

    body = json.dumps({"kind": "plot", "items": [_curve("v", "1.75t^2 + 8")]})
    fences = drawn_fences(
        [body], ["Now draw the velocity-time graph.", _U5_088], "", read_graph_facts
    )
    assert fences and "v = 7t²/4 + 8" in fences[0]


def test_a_factored_acceleration_is_read() -> None:
    found = {
        n: e
        for n, e, _u in motion_formulas(
            plain("A particle starts from rest with acceleration (t + 1)(t - 1) m/s². Sketch v.")
        )
    }
    assert "a" in found and (found["a"] - (_t() ** 2 - 1)).equals(0)


def test_a_follow_up_never_mixes_an_older_curve_with_the_motion() -> None:
    import json

    from app.modules.math.drawing.build import drawn_fences

    texts = [
        "Now a particle starts from rest with acceleration 2 m/s^2 for 5 s. Draw the v-t graph.",
        "Sketch y = x^2.",
    ]
    old = json.dumps({"kind": "plot", "items": [_curve("f", "x^2")]})
    assert drawn_fences([old], texts, "", read_graph_facts) == []
    motion = json.dumps({"kind": "plot", "items": [_curve("v", "2t")]})
    fences = drawn_fences([motion], texts, "", read_graph_facts)
    assert fences and "v = 2t" in fences[0]


@pytest.mark.parametrize(
    "question",
    [
        "A car starts from rest with acceleration 2 m/s² for 3 s, then moves with acceleration "
        "-1 m/s² for 4 s. Draw the v-t graph.",
        "A car starts from rest with acceleration 2 m/s² for 3 s and then decelerates to rest. "
        "Draw the v-t graph.",
    ],
)
def test_a_motion_in_phases_gives_no_curve(question: str) -> None:
    # A curve in pieces it does not build: none, never v = 2t over both (PR #2486 review).
    assert read_graph_facts(question).formulas == ()


@pytest.mark.parametrize(
    ("question", "interval"),
    [
        ("From t = 2 s a particle at rest moves with acceleration 3 m/s² for 4 s. Draw the v-t "
         "graph.", ("2", "6")),
        # A time a value is stated at is no start: "for 4 s" is from 0 (PR #2486 review).
        ("A particle moves with acceleration 6t m/s² for 4 s. When t = 2 s its velocity is "
         "15 m/s. Draw the v-t graph.", ("0", "4")),
        ("A particle starts at t = 5 s from rest and moves with acceleration 2 m/s² for 4 s. "
         "Draw the v-t graph.", ("5", "9")),
        ("A car starts from rest with acceleration 2 m/s². Draw the v-t graph for 5 s.",
         ("0", "5")),
    ],
)  # fmt: skip
def test_a_duration_runs_from_the_motion_s_start(question: str, interval: tuple[str, str]) -> None:
    assert read_graph_facts(question).interval == interval


@pytest.mark.parametrize(
    ("question", "formulas"),
    [
        # "at 3 s" is a time; "starts" lends its 0 to no other clause (PR #2486 review).
        ("A particle starts from O with acceleration 2t m/s², and at 3 s its velocity is "
         "10 m/s.", {"a": "2*t", "v": "t**2 + 1", "s": "t**3/3 + t"}),
        # An asked sentence states nothing: its 15 m/s is no v(2).
        ("A particle starts from rest with acceleration 2t m/s². Find (a) the initial "
         "acceleration, (b) the displacement when t = 2 s, (c) the time when its velocity is "
         "15 m/s.", {"a": "2*t", "v": "t**2"}),
        ("A particle starts from rest with acceleration 2t m/s². What is its velocity when "
         "t = 2 s if it is 15 m/s at the end?", {"a": "2*t", "v": "t**2"}),
    ],
)  # fmt: skip
def test_a_time_is_lent_only_by_a_header(question: str, formulas: dict[str, str]) -> None:
    test_the_motion_is_worked_out_from_the_values_it_states(question, formulas)


@pytest.mark.parametrize(
    ("question", "formulas"),
    [
        # An initial state is at t = 0; the 16 m is said when t = 2 s (PR #2486 review).
        ("A particle starting from rest has displacement 16 m when t = 2 s. Its acceleration is "
         "6t m/s². Sketch s against t.", {"a": "6*t", "v": "3*t**2", "s": "t**3 + 8"}),
        ("A particle with initial velocity 5 m/s has displacement 16 m when t = 2 s. Its "
         "acceleration is 2 m/s².", {"a": "2", "v": "2*t + 5", "s": "t**2 + 5*t + 2"}),
        # "until its velocity is 20 m/s" is said at no time: no v(0) = 20.
        ("A car starts from O with constant acceleration 2 m/s² until its velocity is 20 m/s. "
         "Sketch the v-t graph.", {"a": "2"}),
    ],
)  # fmt: skip
def test_an_initial_state_is_at_the_start_and_a_later_one_at_no_time(
    question: str, formulas: dict[str, str]
) -> None:
    test_the_motion_is_worked_out_from_the_values_it_states(question, formulas)


def test_a_stretch_of_displacement_is_of_x_and_a_motion_in_phases_has_none() -> None:
    from app.modules.math.drawing.plot_question import read_plot_question

    question = (
        "A particle moves from rest with constant acceleration 2 m/s² through a displacement "
        "of 16 m, where x is the displacement. Draw the velocity-time graph."
    )
    facts = read_graph_facts(question)
    assert (facts.letter, facts.interval) == ("x", ("0", "16"))
    # Its v-t graph is in t: the 16 m grounds no t = 16 (PR #2486 review).
    read = read_plot_question([question], read_graph_facts)
    assert all(16 not in (i.low, i.high) for i in read.intervals)
    phases = (
        "A car starts from rest with acceleration 2 m/s² for 3 s, then moves with acceleration "
        "-1 m/s² for 4 s. Draw the v-t graph."
    )
    assert read_graph_facts(phases).interval is None


def test_a_follow_up_with_its_own_bounds_draws_with_the_question_s_motion() -> None:
    import json

    from app.modules.math.drawing.build import drawn_fences

    # "from t = 0 to t = 5" bounds the graph; it writes no curve (PR #2486 review).
    asked = _U5_088.split(" Draw")[0]
    body = json.dumps({"kind": "plot", "items": [_curve("v", "1.75t^2 + 8", domain=["0", "5"])]})
    texts = ["Now draw the velocity-time graph from t = 0 to t = 5.", asked]
    fences = drawn_fences([body], texts, "", read_graph_facts)
    assert fences and "v = 7t²/4 + 8" in fences[0]
