"""Tests for SymPy math service."""

from __future__ import annotations

import math

import pytest

from app.models.math_schemas import EquationInput, GraphSampleInput, RectangleGeometryInput
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


def test_solve_x_squared_plus_two() -> None:
    result = math_service.solve_equation(EquationInput(lhs="x**2 + 2", rhs="6", variables=["x"]))
    joined = " ".join(result.solutions_latex)
    assert "-2" in joined
    assert "2" in joined


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


def test_try_extract_equation() -> None:
    eq = math_service.try_extract_equation_from_text("Solve x^2 + 2 = 6")
    assert eq is not None
    assert eq.lhs.replace(" ", "") in {"x**2+2", "x^2+2"} or "2" in eq.lhs
