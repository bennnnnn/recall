"""Tests for SymPy math service."""

from __future__ import annotations

import math

import pytest

from app.models.math_schemas import (
    EquationInput,
    GraphBlockSpec,
    GraphSampleInput,
    RectangleGeometryInput,
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


def test_try_extract_equation() -> None:
    eq = math_service.try_extract_equation_from_text("Solve x^2 + 2 = 6")
    assert eq is not None
    assert eq.lhs.replace(" ", "") in {"x**2+2", "x^2+2"} or "2" in eq.lhs


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
