"""Tests for SymPy math service."""

from __future__ import annotations

import math

import pytest

from app.models.math_schemas import (
    EquationInput,
    GraphBlockSpec,
    GraphSampleInput,
    RectangleGeometryInput,
    SystemOfEquationsInput,
)
from app.services import math_service


@pytest.mark.parametrize(
    "lhs, rhs, expected_count",
    [
        ("x**2 + 2", "6", 2),
        ("2*x + 4", "10", 1),
    ],
)
def test_solve_equation(lhs: str, rhs: str, expected_count: int) -> None:
    result = math_service.solve_equation(EquationInput(lhs=lhs, rhs=rhs, variables=["x"]))
    assert len(result.solutions_latex) == expected_count
    assert "x" in result.solutions_latex[0]


@pytest.mark.parametrize(
    "lhs, rhs",
    [
        ("x", "x"),
        ("2*x + 4", "2*(x + 2)"),
    ],
)
def test_solve_equation_identifies_infinite_solutions(lhs: str, rhs: str) -> None:
    """BUG FIX: a tautology (true for every value of x) used to collapse
    into the same ambiguous "No solutions found (or infinite solution set)."
    string as a genuine contradiction."""
    result = math_service.solve_equation(EquationInput(lhs=lhs, rhs=rhs, variables=["x"]))
    assert result.solutions_latex == []
    assert result.solution_kind == "infinite"
    assert any("infinitely many" in step.lower() for step in result.steps)


@pytest.mark.parametrize(
    "lhs, rhs",
    [
        ("x", "x + 1"),
        ("0", "1"),
    ],
)
def test_solve_equation_identifies_no_solution(lhs: str, rhs: str) -> None:
    """BUG FIX: a genuine contradiction used to collapse into the same
    ambiguous "No solutions found (or infinite solution set)." string as a
    tautology with infinitely many solutions."""
    result = math_service.solve_equation(EquationInput(lhs=lhs, rhs=rhs, variables=["x"]))
    assert result.solutions_latex == []
    assert result.solution_kind == "none"
    assert any("contradiction" in step.lower() for step in result.steps)


def test_solve_equation_finite_solutions_kind() -> None:
    result = math_service.solve_equation(EquationInput(lhs="2*x + 4", rhs="10", variables=["x"]))
    assert result.solution_kind == "finite"


def test_solve_x_squared_plus_two() -> None:
    result = math_service.solve_equation(EquationInput(lhs="x**2 + 2", rhs="6", variables=["x"]))
    joined = " ".join(result.solutions_latex)
    assert "-2" in joined
    assert "2" in joined


def test_solve_quadratic_includes_worked_isolation_steps() -> None:
    """The user's x^2 + 2 = 6 case: SymPy must emit the verified intermediate
    steps (isolate x^2 = 4, take square root x = ±2) so the model copies them
    instead of inventing wrong steps like 'x^2 = 6 - 2x^2'."""
    result = math_service.solve_equation(EquationInput(lhs="x**2 + 2", rhs="6", variables=["x"]))
    steps_text = "\n".join(result.steps)
    # Isolation step: x^2 = 4
    assert "x^{2} = 4" in steps_text
    # Square-root step: x = ± 2
    assert "\\pm 2" in steps_text
    # No stray wrong terms the model was emitting.
    assert "2x" not in steps_text
    assert "\\sqrt{4x}" not in steps_text


def test_solve_linear_includes_worked_isolation_steps() -> None:
    result = math_service.solve_equation(EquationInput(lhs="2*x + 4", rhs="10", variables=["x"]))
    steps_text = "\n".join(result.steps)
    # 2*x = 6  →  x = 3
    assert "2" in steps_text
    assert "x = 3" in steps_text


def test_worked_steps_empty_for_unrecognized_form() -> None:
    """A multi-variable or higher-degree form gets no worked steps (caller
    still has the equation + solutions)."""
    result = math_service.solve_equation(EquationInput(lhs="x**3 + x", rhs="2", variables=["x"]))
    # Only the Equation: line + Solutions: line — no Isolate/Solve steps.
    assert not any(s.startswith("Isolate:") for s in result.steps)


def test_rectangle_geometry() -> None:
    result = math_service.rectangle_geometry(RectangleGeometryInput(width=8, height=5))
    assert result.diagonal == pytest.approx(math.sqrt(89), rel=1e-3)
    assert result.angle_deg == pytest.approx(math.degrees(math.atan2(5, 8)), rel=1e-2)
    assert result.area == 40.0
    assert result.perimeter == 26.0
    assert "8" in result.labels["width"]


def test_square_geometry() -> None:
    from app.models.math_schemas import SquareGeometryInput

    result = math_service.square_geometry(SquareGeometryInput(side=5))
    assert result.area == 25.0
    assert result.perimeter == 20.0
    assert result.diagonal == pytest.approx(5 * math.sqrt(2), rel=1e-3)


def test_triangle_geometry() -> None:
    from app.models.math_schemas import TriangleGeometryInput

    result = math_service.triangle_geometry(TriangleGeometryInput(base=8, height=5))
    assert result.area == 20.0


def test_right_triangle_geometry() -> None:
    from app.models.math_schemas import RightTriangleGeometryInput

    result = math_service.right_triangle_geometry(RightTriangleGeometryInput(base=6, height=4))
    assert result.hypotenuse == pytest.approx(7.2111, rel=1e-3)
    assert result.area == 12.0
    assert "7.21" in result.labels["hypotenuse"]


def test_circle_geometry() -> None:
    from app.models.math_schemas import CircleGeometryInput

    result = math_service.circle_geometry(CircleGeometryInput(radius=4))
    assert result.diameter == 8.0
    assert result.area == pytest.approx(math.pi * 16, rel=1e-4)
    assert result.circumference == pytest.approx(8 * math.pi, rel=1e-4)
    assert "4" in result.labels["radius"]


def test_sample_function_quadratic() -> None:
    result = math_service.sample_function(
        GraphSampleInput(expr="x**2", variable="x", x_min=-2, x_max=2, n=10)
    )
    assert len(result.points) == 10
    assert result.points[0][0] == pytest.approx(-2.0)
    zeroish = min(result.points, key=lambda p: abs(p[1]))
    assert zeroish[1] == pytest.approx(0.0, abs=0.5)


def test_sample_function_splits_segments_at_a_vertical_asymptote() -> None:
    """BUG FIX (verified live): tan(x) over the default range drew a
    near-straight line across the pi/2 asymptote, since naively connecting
    every finite sample crosses straight through the discontinuity. There
    are 6 real tan(x) asymptotes in [-10, 10] (at (n + 0.5)*pi), so a
    correct split produces 7 pieces."""
    result = math_service.sample_function(
        GraphSampleInput(expr="tan(x)", variable="x", x_min=-10, x_max=10, n=200)
    )
    assert len(result.segments) == 7
    # Every point must still be accounted for across the segments (nothing
    # dropped, nothing duplicated).
    assert sum(len(seg) for seg in result.segments) == len(result.points)


@pytest.mark.parametrize("expr", ["x**2", "sin(x)"])
def test_sample_function_does_not_split_a_smooth_function(expr: str) -> None:
    """A smooth function (even one that crosses zero, like sin(x)) must not
    be split — the heuristic only fires on a sign flip where BOTH sides are
    large in magnitude, which a zero-crossing never is."""
    result = math_service.sample_function(
        GraphSampleInput(expr=expr, variable="x", x_min=-10, x_max=10, n=200)
    )
    assert len(result.segments) == 1


def test_simplify_expression() -> None:
    result = math_service.simplify_expression("x + x", "x")
    assert result.result == "2*x"


def test_differentiate_expression() -> None:
    result = math_service.differentiate_expression("x**2", "x")
    assert "2" in result.latex


def test_integrate_expression_marks_closed_form_result_as_solved() -> None:
    result = math_service.integrate_expression("2*x", "x")
    assert result.result == "x**2"
    assert result.solved is True


def test_integrate_expression_marks_unevaluated_integral_as_not_solved() -> None:
    """BUG FIX: integrate_expression can hand back a result that still
    contains a literal unevaluated Integral(...) instead of raising — that
    used to be indistinguishable from a real closed-form answer downstream,
    where it was asserted to the model as "verified, do NOT recompute"."""
    result = math_service.integrate_expression("x**x", "x")
    assert result.solved is False
    assert "Integral" in result.result


@pytest.mark.parametrize(
    "expr, point, expected",
    [
        ("x**2", "3", "9"),
        ("sin(x)/x", "0", "1"),
        ("1/x", "oo", "0"),
        ("1/x", "infinity", "0"),
    ],
)
def test_compute_limit(expr: str, point: str, expected: str) -> None:
    result = math_service.compute_limit(expr, "x", point)
    assert result.result == expected
    assert result.is_infinite is False


def test_compute_limit_marks_a_diverging_limit_as_infinite() -> None:
    result = math_service.compute_limit("1/x", "x", "0")
    assert result.is_infinite is True
    # A two-sided limit at 0 doesn't exist as a finite value (the sides
    # disagree) — SymPy represents that as complex infinity (zoo), which
    # must still render as \infty, not an opaque symbol.
    assert "infty" in result.latex


def test_compute_limit_negative_infinity_point() -> None:
    result = math_service.compute_limit("x", "x", "-infinity")
    assert result.is_infinite is True


def test_evaluate_series_sum_convergent() -> None:
    result = math_service.evaluate_series_sum("1/n**2", "n", "1", "infinity")
    assert result.is_convergent is True
    assert result.is_absolutely_convergent is True
    assert result.is_infinite is False
    assert "pi" in result.result.lower()


def test_evaluate_series_sum_divergent() -> None:
    """BUG FIX target: the harmonic series (sum 1/n) diverges — must be
    flagged as not convergent and as an infinite result, not silently
    presented as a finite value."""
    result = math_service.evaluate_series_sum("1/n", "n", "1", "infinity")
    assert result.is_convergent is False
    assert result.is_infinite is True
    assert result.result == "oo"


def test_evaluate_series_sum_finite_bounds() -> None:
    result = math_service.evaluate_series_sum("n", "n", "1", "10")
    assert result.result == "55"
    assert result.is_infinite is False


def test_try_extract_equation() -> None:
    eq = math_service.try_extract_equation_from_text("Solve x^2 + 2 = 6")
    assert eq is not None
    assert eq.lhs.replace(" ", "") in {"x**2+2", "x^2+2"}


@pytest.mark.parametrize(
    "text, expected_lhs",
    [
        ("Solve x^2 + 2 = 6", "x^2 + 2"),
        ("solve x^2 + 2 = 6", "x^2 + 2"),
        ("what is x^2 + 2 = 6", "x^2 + 2"),
        ("can you solve x^2 + 2 = 6", "x^2 + 2"),
        ("please solve x^2 + 2 = 6", "x^2 + 2"),
        ("x^2 + 2 = 6", "x^2 + 2"),
    ],
)
def test_try_extract_equation_strips_leading_trigger_words(text: str, expected_lhs: str) -> None:
    """BUG FIX (was live): the equation-extraction regex's lhs capture is
    non-greedy, but re.search still tries the EARLIEST possible match start —
    so "Solve x^2 + 2 = 6" swept "Solve" into the extracted lhs. That
    corrupted both the parsed expression (undeclared letters silently became
    new multiplied symbols via SymPy's auto_symbol) and the guessed variable
    list, producing a confidently wrong "verified" answer. Confirmed live:
    'Solve x^2 + 2 = 6' used to solve for a garbage variable and return
    nonsense like "2.71828182845905 S l o v x^{2} + 2 = 6"."""
    eq = math_service.try_extract_equation_from_text(text)
    assert eq is not None
    assert eq.lhs == expected_lhs
    assert eq.variables == ["x"]
    result = math_service.solve_equation(eq)
    assert result.solutions_latex == ["x = -2", "x = 2"]


def test_try_extract_equations_from_text_finds_every_clause() -> None:
    """BUG FIX (most severe correctness bug found in the audit): this used
    to be a single re.search, so only the FIRST equation was ever extracted
    — "solve x+y=5, x-y=1" silently discarded the second clause."""
    pairs = math_service.try_extract_equations_from_text("solve x+y=5, x-y=1")
    assert pairs == [("x+y", "5"), ("x-y", "1")]


def test_try_extract_equations_from_text_strips_system_prefix() -> None:
    pairs = math_service.try_extract_equations_from_text(
        "solve the system of equations x+2y=8, 3x-y=1"
    )
    assert pairs == [("x+2y", "8"), ("3x-y", "1")]


def test_try_extract_equations_from_text_single_equation_unaffected() -> None:
    assert math_service.try_extract_equations_from_text("x + 4 = 10") == [("x + 4", "10")]


def test_try_extract_equations_from_text_no_equation() -> None:
    assert math_service.try_extract_equations_from_text("what's the weather") == []


def test_solve_system_unique_solution() -> None:
    result = math_service.solve_system(
        SystemOfEquationsInput(equations=[("x+y", "5"), ("x-y", "1")], variables=["x", "y"])
    )
    assert result.solution_kind == "finite"
    assert result.solutions == [{"x": "3", "y": "2"}]


def test_solve_system_no_solution() -> None:
    """BUG FIX target: two parallel-line equations (same slope, different
    intercept) have no solution — must not be silently reported as an empty
    solution set with no explanation."""
    result = math_service.solve_system(
        SystemOfEquationsInput(equations=[("x+y", "5"), ("x+y", "10")], variables=["x", "y"])
    )
    assert result.solution_kind == "none"
    assert result.solutions == []


def test_solve_system_infinite_solutions_dependent_equations() -> None:
    """BUG FIX target: a dependent system (the second equation is just the
    first scaled by 2) has infinitely many solutions along a line — SymPy
    returns a non-empty but parametrized solution ({x: 5 - y}) rather than
    an empty list, which must not be mistaken for a single finite answer."""
    result = math_service.solve_system(
        SystemOfEquationsInput(equations=[("x+y", "5"), ("2*x+2*y", "10")], variables=["x", "y"])
    )
    assert result.solution_kind == "infinite"
    assert result.solutions == [{"x": "5 - y"}]


def test_solve_system_infinite_solutions_independent_tautologies() -> None:
    result = math_service.solve_system(
        SystemOfEquationsInput(equations=[("x", "x"), ("y", "y")], variables=["x", "y"])
    )
    assert result.solution_kind == "infinite"


def test_solve_system_three_by_three() -> None:
    result = math_service.solve_system(
        SystemOfEquationsInput(
            equations=[("x+y+z", "6"), ("x-y+z", "2"), ("x+y-z", "0")],
            variables=["x", "y", "z"],
        )
    )
    assert result.solution_kind == "finite"
    assert result.solutions == [{"x": "1", "y": "2", "z": "3"}]


def test_graph_block_spec_allows_a_single_point_but_rejects_empty() -> None:
    """BUG FIX regression: a single point is a legitimate way to mark one
    coordinate (e.g. "plot the point (2, 3)"), not just a degenerate
    function curve — requiring 2+ points made that a validation error,
    replaced with an "Invalid graph block" fallback instead of rendering."""
    GraphBlockSpec(expr="x", points=[[0.0, 0.0], [1.0, 1.0]])
    GraphBlockSpec(expr="(2, 3)", points=[[2.0, 3.0]])
    with pytest.raises(ValueError, match="at least one"):
        GraphBlockSpec(expr="x", points=[])


def test_graph_block_spec_rejects_more_points_than_the_backend_ever_samples() -> None:
    """BUG FIX regression: points had no upper bound, unlike every other
    field in this file — a model reproducing (or fabricating) a ```graph
    fence could claim an unbounded points array. Matches
    GraphSampleInput.n's own cap (le=500)."""
    GraphBlockSpec(expr="x", points=[[float(i), float(i)] for i in range(500)])
    with pytest.raises(ValueError, match="500"):
        GraphBlockSpec(expr="x", points=[[float(i), float(i)] for i in range(501)])


# ── security: parse_expr/eval is not a safe sandbox for untrusted input ──────
#
# BUG FIX (was a live RCE): parse_expr evaluates its input via Python's
# eval() internally. Restricting local_dict to declared variable names only
# stops bare names from resolving to something dangerous — it does nothing
# to stop attribute access on an already-resolved Symbol object. Any of
# these payloads walks the Python class hierarchy to reach something like
# subprocess.Popen and would execute it, reachable from a plain chat message
# via math_tools.py's keyword-triggered intent extraction (no sanitization)
# and independently via the sympy MCP tool. This must stay blocked.
@pytest.mark.parametrize(
    "payload",
    [
        "x.__class__.__bases__[0].__subclasses__()[400]('id', shell=True, stdout=-1).communicate() x",
        "x.__class__",
        "x.__class__.__mro__[1]",
        "(1).__class__.__bases__[0]",
        "x[0]",
        "x[0:1]",
        "getattr(x, '__class__')",
        'x.__class__.__init__.__globals__["__builtins__"]',
        "x; import os",
        "__import__('os').system('id')",
    ],
)
def test_parse_expression_rejects_attribute_and_subscript_gadgets(payload: str) -> None:
    with pytest.raises(math_service.MathServiceError):
        math_service._parse_expression(payload, ["x"])


@pytest.mark.parametrize(
    "expr, variables",
    [
        ("x**2 + 3*x - 5", ["x"]),
        ("sin(x) + cos(x)", ["x"]),
        ("3.14 * x", ["x"]),
        ("sqrt(x**2 + 1)", ["x"]),
        ("log(x, 10)", ["x"]),
        ("x_1 + x_2", ["x_1", "x_2"]),
        ("2*x + 4", ["x"]),
    ],
)
def test_parse_expression_still_accepts_ordinary_math(expr: str, variables: list[str]) -> None:
    """The RCE fix must not collateral-damage normal expressions."""
    math_service._parse_expression(expr, variables)
