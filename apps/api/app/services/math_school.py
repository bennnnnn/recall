"""School homework ops that are not 2D geometry or single-variable calc I."""

from __future__ import annotations

import math

from sympy import (
    Function,
    Rational,
    Symbol,
    cos,
    dsolve,
    factorial,
    latex,
    nsimplify,
    pi,
    simplify,
    sin,
    tan,
)

from app.models.math_schemas import MathExprResult, MatrixInput, MatrixResult
from app.services.math_service import MathServiceError, _parse_expression

_LENGTH_TO_M = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "km": 1000.0,
    "in": 0.0254,
    "inch": 0.0254,
    "inches": 0.0254,
    "ft": 0.3048,
    "feet": 0.3048,
    "foot": 0.3048,
    "yd": 0.9144,
    "mi": 1609.344,
    "mile": 1609.344,
    "miles": 1609.344,
}
_MASS_TO_KG = {
    "mg": 0.000001,
    "g": 0.001,
    "kg": 1.0,
    "lb": 0.45359237,
    "lbs": 0.45359237,
    "oz": 0.028349523125,
}
_TIME_TO_S = {"ms": 0.001, "s": 1.0, "sec": 1.0, "min": 60.0, "hr": 3600.0, "h": 3600.0}


def evaluate_arithmetic(expr: str) -> str:
    parsed = _parse_expression(expr, ["x"])
    if isinstance(parsed, tuple):
        raise MathServiceError("not a numeric arithmetic expression")
    if parsed.free_symbols:
        raise MathServiceError("arithmetic expression still has variables")
    value = simplify(parsed)
    return str(latex(value))


def percent_of(rate: float, base: float) -> str:
    value = (rate / 100.0) * base
    return f"{value:g}"


def simplify_ratio(a: int, b: int) -> str:
    from math import gcd

    g = gcd(a, b)
    return f"{a // g}:{b // g}"


def evaluate_trig_degrees(func: str, degrees: float) -> str:
    table = {"sin": sin, "cos": cos, "tan": tan}
    if func not in table:
        raise MathServiceError(f"unsupported trig function {func}")
    exact = simplify(table[func](nsimplify(degrees) * pi / 180))
    return str(latex(exact))


def coord_distance(x1: float, y1: float, x2: float, y2: float) -> str:
    d = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return f"{d:g}"


def coord_midpoint(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"({(x1 + x2) / 2:g}, {(y1 + y2) / 2:g})"


def coord_slope(x1: float, y1: float, x2: float, y2: float) -> str:
    if x2 == x1:
        return r"\text{undefined}"
    return f"{(y2 - y1) / (x2 - x1):g}"


def vector_magnitude(vec: list[float]) -> str:
    mag = math.sqrt(sum(c * c for c in vec))
    return f"{mag:g}"


def vector_dot(a: list[float], b: list[float]) -> str:
    if len(a) != len(b):
        raise MathServiceError("dot product needs matching dimension")
    return f"{sum(x * y for x, y in zip(a, b, strict=True)):g}"


def vector_cross(a: list[float], b: list[float]) -> str:
    if len(a) == 2:
        a = [a[0], a[1], 0.0]
        b = [b[0], b[1], 0.0]
    if len(a) != 3 or len(b) != 3:
        raise MathServiceError("cross product needs 2D or 3D vectors")
    cx = a[1] * b[2] - a[2] * b[1]
    cy = a[2] * b[0] - a[0] * b[2]
    cz = a[0] * b[1] - a[1] * b[0]
    return f"({cx:g}, {cy:g}, {cz:g})"


def binomial_pmf(n: int, k: int, p: float) -> str:
    if not (0 <= k <= n) or not (0.0 <= p <= 1.0):
        raise MathServiceError("invalid binomial parameters")
    coeff = int(factorial(n) / (factorial(k) * factorial(n - k)))
    value = coeff * (p**k) * ((1.0 - p) ** (n - k))
    return f"{value:g}"


def expected_value(values: list[float], probs: list[float] | None) -> str:
    if not values:
        raise MathServiceError("expected value needs data")
    if probs is None:
        return f"{sum(values) / len(values):g}"
    if len(probs) != len(values):
        raise MathServiceError("values and probabilities must match")
    return f"{sum(v * p for v, p in zip(values, probs, strict=True)):g}"


def _imaginary_unit_to_sympy(expr: str) -> str:
    """Map standalone ``i``/``j`` to SymPy ``I`` without rewriting ``sin``/``pi``.

    A naive ``str.replace("i", "I")`` turns ``sin`` into ``sIn`` and ``pi``
    into ``pI``. Only replace when the letter is not inside an identifier.
    """
    out: list[str] = []
    n = len(expr)
    for idx, ch in enumerate(expr):
        if ch in ("i", "j"):
            prev_letter = idx > 0 and expr[idx - 1].isalpha()
            next_letter = idx + 1 < n and expr[idx + 1].isalpha()
            if not prev_letter and not next_letter:
                out.append("I")
                continue
        out.append(ch)
    return "".join(out)


def evaluate_complex(expr: str) -> str:
    parsed = _parse_expression(_imaginary_unit_to_sympy(expr), ["x"])
    return str(latex(simplify(parsed)))


def convert_unit(value: float, src: str, dest: str) -> str:
    s, d = src.lower().rstrip("s"), dest.lower().rstrip("s")
    if s in {"c", "celsius"} and d in {"f", "fahrenheit"}:
        return f"{value * 9.0 / 5.0 + 32.0:g}"
    if s in {"f", "fahrenheit"} and d in {"c", "celsius"}:
        return f"{(value - 32.0) * 5.0 / 9.0:g}"
    if s in {"c", "celsius"} and d in {"k", "kelvin"}:
        return f"{value + 273.15:g}"
    if s in {"k", "kelvin"} and d in {"c", "celsius"}:
        return f"{value - 273.15:g}"
    for table in (_LENGTH_TO_M, _MASS_TO_KG, _TIME_TO_S):
        if s in table and d in table:
            si = value * table[s]
            return f"{si / table[d]:g}"
    raise MathServiceError(f"unsupported conversion {src} to {dest}")


def taylor_series(expr: str, variable: str, point: str, order: int) -> MathExprResult:
    from sympy import series

    parsed = _parse_expression(expr, [variable])
    var = Symbol(variable)
    pt = _parse_expression(point, [variable])
    out = series(parsed, var, pt, order + 1).removeO()
    tex = str(latex(out))
    return MathExprResult(result=tex, latex=tex, solved=True)


def partial_derivative(expr: str, variable: str) -> MathExprResult:
    from sympy import diff

    parsed = _parse_expression(expr, [variable])
    out = diff(parsed, Symbol(variable))
    tex = str(latex(out))
    return MathExprResult(result=tex, latex=tex, solved=True)


def solve_ode(expr: str, variable: str = "x") -> MathExprResult:
    """First-order ODE: ``dy/dx = ...`` or ``y' = ...`` in ``expr`` as Eq."""
    y = Function("y")
    ivar = Symbol(variable)
    text = expr.replace("y'", f"Derivative(y({variable}), {variable})")
    text = text.replace("dy/dx", f"Derivative(y({variable}), {variable})")
    parsed = _parse_expression(text, [variable])
    try:
        sol = dsolve(parsed, y(ivar))
    except Exception as exc:
        raise MathServiceError("could not solve ODE") from exc
    tex = str(latex(sol))
    return MathExprResult(result=tex, latex=tex, solved=True)


def compute_matrix_extended(data: MatrixInput) -> MatrixResult:
    from sympy import Matrix as SyMatrix

    mat = SyMatrix([[Rational(str(v)) for v in row] for row in data.rows])
    if data.operation == "multiply":
        if data.rows_b is None:
            raise MathServiceError("matrix multiply needs a second matrix")
        other = SyMatrix([[Rational(str(v)) for v in row] for row in data.rows_b])
        product = mat * other
        return MatrixResult(
            operation="multiply",
            result_latex=latex(product),
            steps=[f"AB = {latex(product)}"],
        )
    if data.operation == "rref":
        rref, _pivots = mat.rref()
        return MatrixResult(
            operation="rref",
            result_latex=latex(rref),
            steps=[f"\\mathrm{{rref}} = {latex(rref)}"],
        )
    if data.operation == "eigenvalues":
        if mat.rows != mat.cols:
            raise MathServiceError("eigenvalues need a square matrix")
        eigs = mat.eigenvals()
        parts = [f"{latex(val)}^{{({mult})}}" for val, mult in eigs.items()]
        body = ", ".join(parts)
        return MatrixResult(
            operation="eigenvalues",
            result_latex=body,
            steps=[f"\\lambda = {body}"],
        )
    raise MathServiceError(f"unsupported matrix operation {data.operation}")


def evaluate_trig_expr(expr: str) -> str:
    parsed = _parse_expression(expr.replace("\u00b0", "*pi/180"), ["x"])
    return str(latex(simplify(parsed)))
