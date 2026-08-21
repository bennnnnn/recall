"""Calculus intent extractors."""

from __future__ import annotations

from typing import Literal

from app.models.math_schemas import MathIntent
from app.services.math_tools.helpers import (
    _calc_expr_tail,
    _normalize_latex_expr,
    _strip_series_prefix,
    _strip_trailing_filler,
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
    expr = _strip_trailing_filler(tail) if tail is not None else cleaned
    integral_lower: str | None = None
    integral_upper: str | None = None
    if calc_op == "integrate":
        bounds = mtm.integral_bounds(expr)
        if bounds is not None:
            expr, integral_lower, integral_upper = bounds
    return MathIntent(
        kind="calculus",
        expr=expr,
        operation=calc_op,
        integral_lower=integral_lower,
        integral_upper=integral_upper,
    )


def _extract_limit_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    limit_hit = mtm.parse_limit(cleaned)
    if limit_hit is None:
        return None
    expr = _normalize_latex_expr(_strip_trailing_filler(limit_hit.expr)).replace("^", "**")
    limit_point = limit_hit.point.lstrip("\\")
    if not expr:
        return None
    return MathIntent(
        kind="limit",
        expr=expr,
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
    if not expr:
        return None
    return MathIntent(
        kind="series",
        expr=expr,
        variable=series_hit.var,
        series_start=series_hit.start,
        series_end=end,
        operation="series",
    )


CALCULUS_EXTRACTORS = (
    _extract_calculus_intent,
    _extract_limit_intent,
    _extract_series_intent,
)
