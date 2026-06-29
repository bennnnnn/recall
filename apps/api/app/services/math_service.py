"""Symbolic math via SymPy — server-side only."""

from __future__ import annotations

import logging
import math
import re
from typing import Any

import numpy as np
from sympy import Eq, Symbol, diff, integrate, latex, parse_expr, simplify, solve
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    standard_transformations,
)

from app.models.math_schemas import (
    EquationInput,
    GraphSampleInput,
    GraphSampleResult,
    MathExprResult,
    MathSolveResult,
    RectangleGeometryInput,
    RectangleGeometryResult,
    RightTriangleGeometryInput,
    RightTriangleGeometryResult,
    SquareGeometryInput,
    SquareGeometryResult,
    TriangleGeometryInput,
    TriangleGeometryResult,
)

logger = logging.getLogger(__name__)

_TRANSFORMATIONS = (
    *standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)
_LOCALS: dict[str, Any] = {
    "pi": math.pi,
    "e": math.e,
}


class MathServiceError(ValueError):
    """Invalid or unsupported math input."""


def _normalize_expr(text: str) -> str:
    s = text.strip()
    s = s.replace("^", "**")
    s = re.sub(r"\s+", " ", s)
    return s


def _parse_expression(expr: str, variable_names: list[str] | None = None):
    normalized = _normalize_expr(expr)
    if len(normalized) > 512:
        raise MathServiceError("Expression too long")
    local_dict = dict(_LOCALS)
    if variable_names:
        for name in variable_names:
            local_dict[name] = Symbol(name)
    try:
        return parse_expr(
            normalized,
            local_dict=local_dict,
            transformations=_TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:
        raise MathServiceError(f"Could not parse expression: {expr}") from exc


def parse_equation(data: EquationInput) -> tuple[Any, Any, list[Any]]:
    lhs = _parse_expression(data.lhs, data.variables)
    rhs = _parse_expression(data.rhs, data.variables)
    return Eq(lhs, rhs), lhs, rhs


def solve_equation(data: EquationInput) -> MathSolveResult:
    equation, lhs, rhs = parse_equation(data)
    syms = [Symbol(v) for v in data.variables]
    try:
        raw_solutions = solve(equation, syms, dict=True)
    except Exception as exc:
        raise MathServiceError("Could not solve equation") from exc

    solutions_latex: list[str] = []
    for sol in raw_solutions:
        parts = [f"{latex(sym)} = {latex(val)}" for sym, val in sol.items()]
        solutions_latex.extend(parts)

    if not solutions_latex and raw_solutions:
        solutions_latex = [latex(s) for s in raw_solutions]

    steps = [
        f"Equation: {latex(lhs)} = {latex(rhs)}",
    ]
    if solutions_latex:
        steps.append(f"Solutions: {', '.join(solutions_latex)}")
    else:
        steps.append("No solutions found (or infinite solution set).")

    return MathSolveResult(
        solutions_latex=solutions_latex,
        steps=steps,
        lhs_latex=latex(lhs),
        rhs_latex=latex(rhs),
    )


def simplify_expression(expr: str, variable: str = "x") -> MathExprResult:
    parsed = _parse_expression(expr, [variable])
    result = simplify(parsed)
    return MathExprResult(result=str(result), latex=latex(result))


def differentiate_expression(expr: str, variable: str = "x") -> MathExprResult:
    sym = Symbol(variable)
    parsed = _parse_expression(expr, [variable])
    result = diff(parsed, sym)
    return MathExprResult(result=str(result), latex=latex(result))


def integrate_expression(expr: str, variable: str = "x") -> MathExprResult:
    sym = Symbol(variable)
    parsed = _parse_expression(expr, [variable])
    result = integrate(parsed, sym)
    return MathExprResult(result=str(result), latex=latex(result))


def rectangle_geometry(data: RectangleGeometryInput) -> RectangleGeometryResult:
    w, h = data.width, data.height
    diagonal = math.sqrt(w * w + h * h)
    angle_deg = math.degrees(math.atan2(h, w))
    area = w * h
    perimeter = 2 * (w + h)
    unit = data.unit
    labels = {
        "width": f"{w:g} {unit}",
        "height": f"{h:g} {unit}",
        "diagonal": f"{diagonal:.2f} {unit}",
        "angle": f"{angle_deg:.1f}°",
        "area": f"{area:g} {unit}²",
        "perimeter": f"{perimeter:g} {unit}",
    }
    return RectangleGeometryResult(
        width=w,
        height=h,
        unit=unit,
        diagonal=round(diagonal, 4),
        angle_deg=round(angle_deg, 2),
        area=round(area, 4),
        perimeter=round(perimeter, 4),
        labels=labels,
    )


def square_geometry(data: SquareGeometryInput) -> SquareGeometryResult:
    s = data.side
    diagonal = math.sqrt(2 * s * s)
    area = s * s
    perimeter = 4 * s
    unit = data.unit
    labels = {
        "side": f"{s:g} {unit}",
        "diagonal": f"{diagonal:.2f} {unit}",
        "area": f"{area:g} {unit}²",
        "perimeter": f"{perimeter:g} {unit}",
    }
    return SquareGeometryResult(
        side=s,
        unit=unit,
        diagonal=round(diagonal, 4),
        area=round(area, 4),
        perimeter=round(perimeter, 4),
        labels=labels,
    )


def triangle_geometry(data: TriangleGeometryInput) -> TriangleGeometryResult:
    b, h = data.base, data.height
    area = 0.5 * b * h
    unit = data.unit
    labels = {
        "base": f"{b:g} {unit}",
        "height": f"{h:g} {unit}",
        "area": f"{area:g} {unit}²",
    }
    return TriangleGeometryResult(
        base=b,
        height=h,
        unit=unit,
        area=round(area, 4),
        labels=labels,
    )


def right_triangle_geometry(data: RightTriangleGeometryInput) -> RightTriangleGeometryResult:
    b, h = data.base, data.height
    hypotenuse = math.sqrt(b * b + h * h)
    area = 0.5 * b * h
    unit = data.unit
    labels = {
        "base": f"{b:g} {unit}",
        "height": f"{h:g} {unit}",
        "hypotenuse": f"{hypotenuse:.2f} {unit}",
        "area": f"{area:g} {unit}²",
        "angle": "90°",
    }
    return RightTriangleGeometryResult(
        base=b,
        height=h,
        unit=unit,
        hypotenuse=round(hypotenuse, 4),
        area=round(area, 4),
        labels=labels,
    )


def sample_function(data: GraphSampleInput) -> GraphSampleResult:
    if data.x_max <= data.x_min:
        raise MathServiceError("x_max must be greater than x_min")
    sym = Symbol(data.variable)
    parsed = _parse_expression(data.expr, [data.variable])

    from sympy.utilities.lambdify import lambdify

    numpy_fn = lambdify(sym, parsed, modules=["numpy"])
    xs = np.linspace(data.x_min, data.x_max, data.n)
    try:
        ys = numpy_fn(xs)
    except Exception as exc:
        raise MathServiceError(f"Could not sample function: {data.expr}") from exc

    ys = np.asarray(ys, dtype=float)
    points: list[list[float]] = []
    for x_val, y_val in zip(xs, ys, strict=False):
        if not np.isfinite(y_val):
            continue
        points.append([round(float(x_val), 4), round(float(y_val), 4)])

    return GraphSampleResult(
        expr=data.expr,
        variable=data.variable,
        x_min=data.x_min,
        x_max=data.x_max,
        points=points,
    )


def try_extract_equation_from_text(text: str) -> EquationInput | None:
    """Best-effort equation extraction from user text."""
    cleaned = text.strip()
    patterns = [
        r"(?P<lhs>[0-9a-zA-Z+\-*/().\s^**]+?)\s*=\s*(?P<rhs>[0-9a-zA-Z+\-*/().\s^**]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue
        lhs = match.group("lhs").strip()
        rhs = match.group("rhs").strip()
        if not lhs or not rhs or len(lhs) > 120 or len(rhs) > 120:
            continue
        variables = _guess_variables(lhs + rhs)
        try:
            return EquationInput(lhs=lhs, rhs=rhs, variables=variables or ["x"])
        except Exception:
            continue
    return None


def _guess_variables(text: str) -> list[str]:
    found = sorted(set(re.findall(r"[a-zA-Z]", text)))
    letters = [c for c in found if c not in {"e"}]
    return letters[:4] if letters else ["x"]
