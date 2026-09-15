"""Verified single-variable calculus applications.

These helpers use Recall's restricted SymPy parser and fail closed whenever a
finite closed-form result cannot be established.
"""

from __future__ import annotations

import math

from sympy import Eq, Expr, FiniteSet, Integral, Interval, S, Symbol, integrate, pi, simplify, solveset, sqrt
from sympy.calculus.util import continuous_domain

from app.services.math.solve.parse import MathServiceError, _parse_expression, format_verified_latex


def _expr(text: str) -> Expr:
    return _parse_expression(text, ["x"], real=True)


def _bound(text: str) -> Expr:
    return _parse_expression(text, [], real=True)


def _ordered_bounds(lower: str, upper: str) -> tuple[Expr, Expr]:
    lo = _bound(lower)
    hi = _bound(upper)
    try:
        width = float((hi - lo).evalf())
    except (TypeError, ValueError, OverflowError) as exc:
        raise MathServiceError("integration bounds must be finite ordered real values") from exc
    if not math.isfinite(width) or width <= 0:
        raise MathServiceError("upper bound must be greater than lower bound")
    return lo, hi


def _closed_integral(value: Expr, label: str) -> str:
    if value.has(Integral):
        raise MathServiceError(f"no closed-form {label} was found")
    if value in {S.NaN, S.ComplexInfinity, S.Infinity, S.NegativeInfinity}:
        raise MathServiceError(f"{label} is not finite")
    return format_verified_latex(simplify(value))


def _require_continuous(expr: Expr, variable: Symbol, lower: Expr, upper: Expr) -> None:
    interval = Interval(lower, upper)
    try:
        domain = continuous_domain(expr, variable, S.Reals)
    except NotImplementedError as exc:
        raise MathServiceError("could not verify continuity on the requested interval") from exc
    if interval.is_subset(domain) is not True:
        raise MathServiceError("the expression is not continuous on the requested interval")


def _integrate_absolute(expr: Expr, variable: Symbol, lower: Expr, upper: Expr) -> Expr:
    """Integrate |expr| by splitting at verified real zeros in the interval."""
    if simplify(expr) == 0:
        return S.Zero
    interval = Interval(lower, upper)
    try:
        root_set = solveset(Eq(expr, 0), variable, domain=interval)
    except Exception as exc:
        raise MathServiceError("could not locate the curve crossings symbolically") from exc
    if not isinstance(root_set, FiniteSet):
        raise MathServiceError("could not enumerate every crossing on the requested interval")
    roots = list(root_set)
    if len(roots) > 32:
        raise MathServiceError("too many curve crossings to verify safely")

    lo_float = float(lower.evalf())
    hi_float = float(upper.evalf())
    internal: list[tuple[float, Expr]] = []
    for root in roots:
        if root.has(variable) or root.is_real is False:
            continue
        try:
            root_float = float(root.evalf())
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(root_float) and lo_float < root_float < hi_float:
            if not any(abs(root_float - seen) < 1e-10 for seen, _ in internal):
                internal.append((root_float, root))
    internal.sort(key=lambda item: item[0])

    points = [lower, *(root for _, root in internal), upper]
    total = S.Zero
    for index in range(len(points) - 1):
        left = points[index]
        right = points[index + 1]
        midpoint = simplify((left + right) / 2)
        try:
            sign = float(expr.subs(variable, midpoint).evalf())
        except (TypeError, ValueError, OverflowError) as exc:
            raise MathServiceError("could not determine the sign between crossings") from exc
        if not math.isfinite(sign):
            raise MathServiceError("the integrand is not finite between the requested bounds")
        piece = integrate(expr, (variable, left, right))
        if piece.has(Integral):
            raise MathServiceError("no closed-form integral was found")
        total += -piece if sign < 0 else piece
    return simplify(total)


def solve_calculus_application(
    operation: str,
    expr_text: str,
    lower: str,
    upper: str,
    expr2_text: str | None = None,
) -> str:
    """Solve a supported geometric application of a definite integral."""
    x = Symbol("x", real=True)
    expr = _expr(expr_text)
    lo, hi = _ordered_bounds(lower, upper)
    _require_continuous(expr, x, lo, hi)

    if operation == "area_between_curves":
        if expr2_text is None:
            raise MathServiceError("area between curves needs two functions")
        other = _expr(expr2_text)
        _require_continuous(other, x, lo, hi)
        result = _integrate_absolute(expr - other, x, lo, hi)
        return _closed_integral(result, "area")

    if operation == "arc_length":
        result = integrate(sqrt(1 + expr.diff(x) ** 2), (x, lo, hi))
        return _closed_integral(result, "arc length")

    if operation == "volume_revolution_x":
        result = pi * integrate(expr**2, (x, lo, hi))
        return _closed_integral(result, "volume")

    if operation == "volume_revolution_y":
        lo_float = float(lo.evalf())
        hi_float = float(hi.evalf())
        if lo_float < 0 < hi_float:
            raise MathServiceError(
                "verified y-axis shell volume requires an interval on one side of the axis"
            )
        shells = _integrate_absolute(x * expr, x, lo, hi)
        return _closed_integral(2 * pi * shells, "volume")

    raise MathServiceError(f"unsupported calculus application: {operation}")
