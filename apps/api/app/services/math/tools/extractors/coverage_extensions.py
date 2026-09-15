"""Strict extractors for small verified coverage extensions."""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
from app.services.math.match.discrete import bracket_matrices
from app.services.math.tools.helpers import _strip_trailing_filler, math_expr_or_none


def _extract_function_parity_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "even or odd" not in lower and "odd or even" not in lower:
        return None
    match = re.search(
        r"(?:f\s*\(\s*([a-zA-Z])\s*\)|y)\s*=\s*(.+?)"
        r"(?=\s+(?:is\s+)?(?:even|odd)\b|[?.!]*$)",
        cleaned,
        re.IGNORECASE,
    )
    if match is None:
        return None
    variable = match.group(1) or "x"
    expr = math_expr_or_none(_strip_trailing_filler(match.group(2)))
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        school_op="function_even_odd",
        expr=expr,
        variable=variable,
        operation="simplify",
    )


def _extract_matrix_extension_intent(cleaned: str) -> MathIntent | None:
    if "[[" not in cleaned:
        return None
    lower = cleaned.lower()
    if (
        "nullity" in lower
        or "dimension of the null space" in lower
        or "dimension of null space" in lower
    ):
        operation = "matrix_nullity"
    elif "linearly independent" in lower and (
        "column" in lower or "columns" in lower
    ):
        operation = "matrix_independent_columns"
    else:
        return None
    matrices = bracket_matrices(cleaned, limit=2)
    if not matrices or len(matrices) != 1:
        return None
    return MathIntent(
        kind="matrix",
        school_op=operation,
        matrix_rows=matrices[0],
        operation="solve",
    )


COVERAGE_EXTENSION_EXTRACTORS = (
    _extract_function_parity_intent,
    _extract_matrix_extension_intent,
)
