"""Calculus intent extractors."""

from __future__ import annotations

from typing import Literal

from app.models.math_schemas import MathIntent
from app.services.math_tools.helpers import (
    _calc_expr_tail,
    _normalize_latex_expr,
    _strip_series_prefix,
    _strip_trailing_filler,
    math_expr_or_none,
    peel_function_definition,
)


def _derivative_order(cleaned: str) -> int:
    """1-3 from phrasing. Linear scans — no regex."""
    low = cleaned.lower()
    for phrase, order in (
        ("third derivative", 3),
        ("3rd derivative", 3),
        ("second derivative", 2),
        ("2nd derivative", 2),
    ):
        if phrase in low:
            return order
    compact = low.replace(" ", "")
    if "d^3" in compact or "d³" in compact:
        return 3
    if "d^2" in compact or "d²" in compact:
        return 2
    return 1


def _extract_critical_points_intent(cleaned: str) -> MathIntent | None:
    """Intercept extrema asks so they cannot fall through to a fake equation solve."""
    low = cleaned.lower()
    if (
        "critical point" not in low
        and "extrema" not in low
        and "local max" not in low
        and "local min" not in low
    ):
        return None
    from app.services import math_service

    expr: str | None = None
    pairs = math_service.try_extract_equations_from_text(cleaned)
    if pairs:
        _lhs, rhs = pairs[0]
        expr = math_expr_or_none(rhs)
    if expr is None:
        of_at = low.find(" of ")
        if of_at != -1:
            expr = math_expr_or_none(_strip_trailing_filler(cleaned[of_at + 4 :]))
    return MathIntent(
        kind="calculus",
        expr=expr or "",
        operation="critical_points",
        variable="x",
    )


def _extract_calculus_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    op_word = mtm.calc_op(cleaned)
    if op_word is None or op_word in {"taylor", "partial", "dsolve"}:
        return None
    calc_op: Literal["simplify", "differentiate", "integrate", "factor", "expand"] = (
        "differentiate" if op_word in {"differentiate", "derivative"} else "integrate"
    )
    if op_word == "simplify":
        calc_op = "simplify"
    elif op_word == "factor":
        calc_op = "factor"
    elif op_word == "expand":
        calc_op = "expand"
    tail = _calc_expr_tail(cleaned)
    raw = _strip_trailing_filler(tail) if tail is not None else cleaned
    raw = peel_function_definition(raw)
    # ``simplify 4x+2x=18`` is an equation, not a simplify-of-equality. Fall
    # through so the algebra extractor can solve it. Explicit factor/expand
    # of a single ``poly=0`` stays calculus; a worked multi-equation paste
    # (`Factor it:` then 2x-1=0) must not steal the quadratic.
    if calc_op == "simplify" and "=" in raw:
        return None
    if calc_op in {"factor", "expand"} and "=" in raw:
        from app.services import math_service

        pairs = math_service.try_extract_equations_from_text(cleaned)
        if len(pairs) >= 2:
            return None
        if pairs and pairs[0][1].strip() in {"0", "0.0"}:
            raw = pairs[0][0]
    integral_lower: str | None = None
    integral_upper: str | None = None
    if calc_op == "integrate":
        bounds = mtm.integral_bounds(raw)
        if bounds is not None:
            raw, integral_lower, integral_upper = bounds
    expr = math_expr_or_none(raw)
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        expr=expr,
        operation=calc_op,
        integral_lower=integral_lower,
        integral_upper=integral_upper,
        derivative_order=_derivative_order(cleaned) if calc_op == "differentiate" else 1,
    )


def _extract_limit_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    limit_hit = mtm.parse_limit(cleaned)
    if limit_hit is None:
        return None
    expr = _normalize_latex_expr(_strip_trailing_filler(limit_hit.expr)).replace("^", "**")
    limit_point = limit_hit.point.lstrip("\\")
    guarded = math_expr_or_none(expr)
    if guarded is None:
        return None
    return MathIntent(
        kind="limit",
        expr=guarded,
        variable=limit_hit.var,
        limit_point=limit_point,
        operation="limit",
    )


def _extract_series_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    series_hit = mtm.parse_series(cleaned)
    if series_hit is None:
        return None
    expr = _normalize_latex_expr(
        _strip_series_prefix(_strip_trailing_filler(series_hit.expr))
    ).replace("^", "**")
    end = series_hit.end.lstrip("\\")
    guarded = math_expr_or_none(expr)
    if guarded is None:
        return None
    return MathIntent(
        kind="series",
        expr=guarded,
        variable=series_hit.var,
        series_start=series_hit.start,
        series_end=end,
        operation="series",
    )


CALCULUS_EXTRACTORS = (
    _extract_critical_points_intent,
    _extract_calculus_intent,
    _extract_limit_intent,
    _extract_series_intent,
)
