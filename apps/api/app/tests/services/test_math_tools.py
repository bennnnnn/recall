"""Tests for math tools heuristics and prompt injection."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services import math_tools


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Solve x^2 + 2 = 6", True),
        ("What's the weather?", False),
        ("A rectangle is 8×5 cm. Find the diagonal angle.", True),
        ("Graph y = x^2", True),
        ("Draw a rectangle", True),
    ],
)
def test_needs_symbolic_math(text: str, expected: bool) -> None:
    assert math_tools.needs_symbolic_math(text) is expected


def test_extract_equation_intent() -> None:
    intent = math_tools.extract_math_intent("Solve x^2 + 2 = 6")
    assert intent is not None
    assert intent.kind == "equation"
    assert intent.lhs == "x^2 + 2"
    assert intent.rhs == "6"
    assert intent.variable == "x"


def test_extract_system_intent_for_multiple_equations() -> None:
    """BUG FIX (most severe correctness bug found in the audit): before this
    fix, a message with 2+ equations fell through to the single-equation
    branch, which only ever looked at the first clause."""
    intent = math_tools.extract_math_intent("solve x+y=5, x-y=1")
    assert intent is not None
    assert intent.kind == "system"
    assert intent.system_equations == [("x+y", "5"), ("x-y", "1")]
    assert intent.system_variables is not None
    assert set(intent.system_variables) >= {"x", "y"}


@pytest.mark.asyncio
async def test_augment_prompt_injects_system_solve_block() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "solve x+y=5, x-y=1"
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "Equation 1:" in verified.text
    assert "Equation 2:" in verified.text
    assert "x = 3" in verified.text
    assert "y = 2" in verified.text
    assert any("x = 3" in m["content"] for m in out if m["role"] == "system")


@pytest.mark.asyncio
async def test_augment_prompt_system_flags_inconsistent_equations() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "solve x+y=5, x+y=10"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "inconsistent" in verified.text.lower()


def test_extract_rectangle_intent() -> None:
    intent = math_tools.extract_math_intent("rectangle 8 x 5 cm find diagonal")
    assert intent is not None
    assert intent.kind == "rectangle"
    assert intent.width == 8
    assert intent.height == 5


def test_extract_draw_rectangle_defaults() -> None:
    intent = math_tools.extract_math_intent("Draw a rectangle")
    assert intent is not None
    assert intent.kind == "rectangle"
    assert intent.width == 6
    assert intent.height == 4


@pytest.mark.parametrize(
    "text, wants_diagonal, wants_angle, wants_area, wants_perimeter",
    [
        ("rectangle area with 4 by 5", False, False, True, False),
        ("rectangle 8 x 5 cm find diagonal", True, False, False, False),
        ("rectangle 8 x 5 cm diagonal angle", True, True, False, False),
        ("rectangle perimeter 4 by 5", False, False, False, True),
        ("rectangle 4 by 5", False, False, False, False),
    ],
)
def test_extract_rectangle_intent_captures_what_was_asked(
    text: str, wants_diagonal: bool, wants_angle: bool, wants_area: bool, wants_perimeter: bool
) -> None:
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.wants_diagonal is wants_diagonal
    assert intent.wants_angle is wants_angle
    assert intent.wants_area is wants_area
    assert intent.wants_perimeter is wants_perimeter


def test_extract_circle_radius_intent() -> None:
    intent = math_tools.extract_math_intent("Draw a circle with radius 4 cm")
    assert intent is not None
    assert intent.kind == "circle"
    assert intent.radius == 4


def test_extract_circle_diameter_intent() -> None:
    intent = math_tools.extract_math_intent("circle diameter 10")
    assert intent is not None
    assert intent.kind == "circle"
    assert intent.radius == 5
    assert intent.wants_diameter is True


def test_extract_circle_intent_defaults_without_dims() -> None:
    intent = math_tools.extract_math_intent("Draw a circle")
    assert intent is not None
    assert intent.kind == "circle"
    assert intent.radius == 5


@pytest.mark.parametrize(
    "text",
    [
        "(2,3)",
        "(2, 3)",
        "(2.3)",  # BUG FIX: comma-for-period mobile keyboard slip
        "(-2, 3)",
        "plot the point (2, 3)",
        "mark point 2, 3",
    ],
)
def test_extract_bare_point_intent(text: str) -> None:
    """BUG FIX regression: a bare coordinate pair (e.g. answering "what
    point?" with "(2,3)") had no intent detection at all, so the model was
    left to freely improvise — observed inventing an unrequested line
    (y=1.5x) that merely happens to pass through the point instead of
    marking the point itself."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "point"
    assert intent.point_x == pytest.approx(-2.0 if text.startswith("(-2") else 2.0)
    assert intent.point_y == pytest.approx(3.0)


def test_bare_point_does_not_misfire_on_prose_with_a_decimal_in_parens() -> None:
    """The whole-message match requirement keeps this from misfiring on
    ordinary prose that happens to contain a parenthesized decimal."""
    intent = math_tools.extract_math_intent("The result is about (2.3) give or take")
    assert intent is None or intent.kind != "point"


def test_extract_square_intent() -> None:
    intent = math_tools.extract_math_intent("Draw a square with side 5 cm")
    assert intent is not None
    assert intent.kind == "square"
    assert intent.side == 5


@pytest.mark.parametrize(
    "text, expected_expr",
    [
        ("graph x^2 please", "x**2"),
        ("graph x^2 for me", "x**2"),
        ("plot sin(x) and explain it", "sin(x)"),
        ("can you graph x^2 now", "x**2"),
    ],
)
def test_extract_graph_intent_strips_trailing_prose(text: str, expected_expr: str) -> None:
    """BUG FIX regression: the graph-expr capture is greedy, so natural
    phrasing ('graph x^2 please') used to sweep trailing conversational
    words into the "expression" — which then failed to parse in SymPy and
    silently disabled the verified-graph augmentation entirely."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "graph"
    assert intent.expr == expected_expr


@pytest.mark.parametrize(
    "text, expected_expr",
    [
        ("differentiate x^2 please", "x^2"),
        ("integrate x^2 for me", "x^2"),
        ("simplify x^2 + 2x + x^2 now", "x^2 + 2x + x^2"),
    ],
)
def test_extract_calculus_intent_strips_trailing_prose(text: str, expected_expr: str) -> None:
    """Same bug as the graph case, for the calculus expr-match capture."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "calculus"
    assert intent.expr == expected_expr


@pytest.mark.parametrize(
    "text, expected_expr, expected_var, expected_point",
    [
        ("find the limit of x^2 as x approaches 3", "x**2", "x", "3"),
        ("limit of sin(x)/x as x approaches 0", "sin(x)/x", "x", "0"),
        ("what is the limit of 1/x as x approaches infinity", "1/x", "x", "infinity"),
        ("evaluate the limit of (x^2-1)/(x-1) as x -> 1", "(x**2-1)/(x-1)", "x", "1"),
        ("lim x->0 sin(x)/x", "sin(x)/x", "x", "0"),
        (r"\lim_{x \to 0} \sin(x)/x", "sin(x)/x", "x", "0"),
    ],
)
def test_extract_limit_intent(
    text: str, expected_expr: str, expected_var: str, expected_point: str
) -> None:
    assert math_tools.needs_symbolic_math(text) is True
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "limit"
    assert intent.expr == expected_expr
    assert intent.variable == expected_var
    assert intent.limit_point == expected_point


def test_limit_regex_does_not_misfire_on_unrelated_approaches_prose() -> None:
    """The word "approaches" alone (without "limit"/"lim") must not trigger
    symbolic math — e.g. "the deadline as it approaches Friday" is not math."""
    assert math_tools.needs_symbolic_math("the deadline as it approaches Friday") is False


@pytest.mark.parametrize(
    "text, expected_expr, expected_var, expected_start, expected_end",
    [
        (
            "does the series sum of 1/n^2 from n=1 to infinity converge",
            "1/n**2",
            "n",
            "1",
            "infinity",
        ),
        ("evaluate the sum of 1/2^n from n=0 to infinity", "1/2**n", "n", "0", "infinity"),
        ("sum of n from n=1 to 10", "n", "n", "1", "10"),
        (r"\sum_{n=1}^{\infty} 1/n^2", "1/n**2", "n", "1", "infty"),
    ],
)
def test_extract_series_intent(
    text: str, expected_expr: str, expected_var: str, expected_start: str, expected_end: str
) -> None:
    assert math_tools.needs_symbolic_math(text) is True
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "series"
    assert intent.expr == expected_expr
    assert intent.variable == expected_var
    assert intent.series_start == expected_start
    assert intent.series_end == expected_end


@pytest.mark.asyncio
async def test_augment_prompt_injects_limit_block() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "find the limit of x^2 as x approaches 3"
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "Result: 9" in verified.text
    assert any("Result: 9" in m["content"] for m in out if m["role"] == "system")


@pytest.mark.asyncio
async def test_augment_prompt_flags_diverging_limit_as_infinite() -> None:
    """BUG FIX target: a limit that diverges (e.g. 1/x as x -> 0) must be
    flagged as infinite, not presented as an ordinary finite value."""
    settings = Settings(math_tools_enabled=True)
    text = "what is the limit of 1/x as x approaches 0"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "infinite" in verified.text.lower()


@pytest.mark.asyncio
async def test_augment_prompt_injects_series_block_with_convergence() -> None:
    settings = Settings(math_tools_enabled=True)
    text = r"\sum_{n=1}^{\infty} 1/n^2"
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "Convergent: True" in verified.text
    assert any("Convergent: True" in m["content"] for m in out if m["role"] == "system")


@pytest.mark.asyncio
async def test_augment_prompt_flags_divergent_series() -> None:
    """BUG FIX target: the harmonic series (sum 1/n) diverges — the model
    must be told it diverges/is infinite, not shown a plausible finite
    number it would otherwise be tempted to invent."""
    settings = Settings(math_tools_enabled=True)
    text = "does the series sum of 1/n from n=1 to infinity converge"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "Convergent: False" in verified.text
    assert "diverges" in verified.text.lower()


@pytest.mark.asyncio
async def test_augment_prompt_injects_geometry_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "rectangle 8 x 5 cm diagonal angle"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "rectangle 8 x 5 cm diagonal angle",
        settings,
    )
    assert len(out) == 2
    assert "```geometry" in out[0]["content"]
    assert "diagonal" in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "rectangle"


@pytest.mark.asyncio
async def test_augment_prompt_rectangle_area_query_does_not_force_diagonal_and_angle() -> None:
    """BUG FIX regression: the rectangle geometry block always set
    show_diagonal=True, show_angle=True regardless of what was asked, so a
    plain "rectangle area 4 by 5" query drew an unrequested diagonal plus a
    diagonal-vs-base angle that visually contradicted the rectangle's own
    (always 90°) corner. The diagram should only annotate what was asked."""
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "What about rectangle area with 4 by 5"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "What about rectangle area with 4 by 5",
        settings,
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["show_diagonal"] is False
    assert verified.canonical_fence["show_angle"] is False
    assert verified.canonical_fence["show_area"] is True
    assert verified.canonical_fence["show_perimeter"] is False


@pytest.mark.asyncio
async def test_augment_prompt_injects_circle_geometry_block() -> None:
    """BUG FIX regression: circles were never a supported geometry kind
    anywhere in the pipeline — the model's own improvised ```geometry
    {"type":"circle",...} fence had no SymPy-verified values and no schema
    to validate against. Now a direct "circle radius 4" gets the same
    verified-computation treatment as every other shape."""
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "circle radius 4 area circumference"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "circle radius 4 area circumference",
        settings,
    )
    assert len(out) == 2
    assert "```geometry" in out[0]["content"]
    assert '"type":"circle"' in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "circle"
    assert verified.canonical_fence["show_area"] is True
    assert verified.canonical_fence["show_circumference"] is True


@pytest.mark.asyncio
async def test_augment_prompt_injects_single_point_graph_block() -> None:
    """BUG FIX regression: a bare "(2,3)" reply (e.g. answering "what
    point?") had no augmentation at all, so the model was free to invent
    an unrequested line through the point instead of just marking it.
    Now it gets a verified single-point ```graph fence with an explicit
    instruction not to invent a function through it."""
    settings = Settings(math_tools_enabled=True)
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "(2,3)"}],
        "(2,3)",
        settings,
    )
    assert len(out) == 2
    assert "```graph" in out[0]["content"]
    assert "Do NOT" in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["points"] == [[2.0, 3.0]]


@pytest.mark.asyncio
async def test_augment_prompt_injects_graph_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "Graph y = x^2"}]
    out, verified = await math_tools.augment_prompt_messages(messages, "Graph y = x^2", settings)
    assert len(out) == 2
    assert "```graph" in out[0]["content"]
    assert "points" in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "function"


@pytest.mark.asyncio
async def test_augment_prompt_attaches_segments_and_warns_on_discontinuous_graph() -> None:
    """BUG FIX (verified live): tan(x) over the default range drew a
    near-straight line across the pi/2 asymptote. The canonical fence must
    carry the split segments, and the model must be told not to describe it
    as one continuous curve."""
    settings = Settings(math_tools_enabled=True)
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Graph tan(x)"}], "Graph tan(x)", settings
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert len(verified.canonical_fence["segments"]) == 7
    assert "discontinuity" in verified.text.lower()
    assert any("discontinuity" in m["content"].lower() for m in out if m["role"] == "system")


@pytest.mark.asyncio
async def test_augment_prompt_omits_segments_for_a_continuous_graph() -> None:
    """The overwhelmingly common case (no discontinuity) must not carry a
    redundant segments field duplicating every point."""
    settings = Settings(math_tools_enabled=True)
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Graph x^2"}], "Graph x^2", settings
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["segments"] == []
    assert "discontinuity" not in verified.text.lower()


@pytest.mark.asyncio
async def test_augment_prompt_flags_unsolved_integral_instead_of_asserting_it() -> None:
    """BUG FIX: integrate_expression can hand back a result that still
    contains a literal unevaluated Integral(...) instead of raising, and this
    used to be injected as "Result: ... Do NOT recompute" — the exact same
    verified-confidence phrasing used for a real closed-form answer. The
    model must be told SymPy found no closed form instead."""
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "integrate x**x"}]
    out, verified = await math_tools.augment_prompt_messages(messages, "integrate x**x", settings)
    assert verified is not None
    assert "Do NOT recompute" not in verified.text
    assert "no closed form" in verified.text.lower() or "not claim" in verified.text.lower()
    assert any("no closed form" in m["content"].lower() for m in out if m["role"] == "system")


@pytest.mark.asyncio
async def test_graph_sample_uses_the_full_configured_point_budget() -> None:
    """BUG FIX regression: a stray `min(..., 200)` silently capped every
    graph at 200 points regardless of math_graph_max_points, so the
    200-300 range of the (default 300) setting was dead code."""
    settings = Settings(math_tools_enabled=True, math_graph_max_points=300)
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Graph y = x^2"}],
        "Graph y = x^2",
        settings,
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert len(verified.canonical_fence["points"]) == 300


@pytest.mark.asyncio
async def test_augment_prompt_injects_sympy_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Solve x^2 + 2 = 6"},
    ]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "Solve x^2 + 2 = 6",
        settings,
    )
    assert len(out) == 3
    assert out[1]["role"] == "system"
    assert "SymPy" in out[1]["content"]
    assert "Solutions" in out[1]["content"]
    # Equation answers are plain-text/LaTeX, not a geometry/graph fence.
    assert verified is not None
    assert verified.canonical_fence is None


@pytest.mark.asyncio
async def test_sympy_solve_runs_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """The blocking SymPy call must not run on the event loop thread."""
    import threading

    settings = Settings(math_tools_enabled=True)
    caller_thread = threading.current_thread()
    seen_thread: dict[str, threading.Thread] = {}

    original = math_tools._build_verified_block

    def spy(intent, settings):  # type: ignore[no-untyped-def]
        seen_thread["thread"] = threading.current_thread()
        return original(intent, settings)

    monkeypatch.setattr(math_tools, "_build_verified_block", spy)

    out, _verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Solve x^2 + 2 = 6"}],
        "Solve x^2 + 2 = 6",
        settings,
    )

    assert seen_thread["thread"] is not caller_thread
    assert len(out) == 2


@pytest.mark.asyncio
async def test_augment_prompt_times_out_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hung solve should fall back to no verified block, not hang the caller."""
    settings = Settings(math_tools_enabled=True, math_solve_timeout_seconds=0.05)

    def slow_build(intent, settings):  # type: ignore[no-untyped-def]
        import time

        time.sleep(0.5)
        return "should never be returned"

    monkeypatch.setattr(math_tools, "_build_verified_block", slow_build)

    messages = [{"role": "user", "content": "Solve x^2 + 2 = 6"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "Solve x^2 + 2 = 6",
        settings,
    )

    assert out == messages
    assert verified is None
