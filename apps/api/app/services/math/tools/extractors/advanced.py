"""Intent extraction for advanced verified math features.

These extractors are intentionally strict. A partial parse is worse than no
verified parse because the verified block instructs the model not to recompute.
"""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
from app.services.math.match.discrete import bracket_matrices, numeric_data_values
from app.services.math.tools.helpers import (
    _strip_trailing_filler,
    math_expr_or_none,
    peel_function_definition,
)

_BOUND = (
    r"[-+]?(?:\d+(?:\.\d+)?|\.\d+|pi|π|e)"
    r"(?:\s*/\s*(?:\d+(?:\.\d+)?|pi|π|e))?"
)
_FROM_TO_RE = re.compile(
    rf"\bfrom\s+(?:x\s*=\s*)?({_BOUND})\s+to\s+(?:x\s*=\s*)?({_BOUND})\b",
    re.IGNORECASE,
)
_ON_INTERVAL_RE = re.compile(
    rf"\bon\s*\[\s*({_BOUND})\s*,\s*({_BOUND})\s*\]",
    re.IGNORECASE,
)


def _clean_expr(raw: str) -> str | None:
    s = _strip_trailing_filler(raw.strip(" ,;"))
    s = peel_function_definition(s)
    while s and s[-1] in ".?!":
        s = s[:-1].rstrip()
    return math_expr_or_none(s)


def _bounds(text: str) -> tuple[str, str, int] | None:
    match = _FROM_TO_RE.search(text)
    if match is None:
        match = _ON_INTERVAL_RE.search(text)
    if match is None:
        return None
    lower = match.group(1).replace("π", "pi")
    upper = match.group(2).replace("π", "pi")
    return lower, upper, match.start()


def _extract_advanced_matrix_intent(cleaned: str) -> MathIntent | None:
    if "[[" not in cleaned:
        return None
    lower = cleaned.lower()
    op: str | None = None
    if "eigenvector" in lower:
        op = "matrix_eigenvectors"
    elif "diagonalize" in lower or "diagonalise" in lower:
        op = "matrix_diagonalize"
    elif (
        "nullity" in lower
        or "dimension of the null space" in lower
        or "dimension of null space" in lower
    ):
        op = "matrix_nullity"
    elif "nullspace" in lower or "null space" in lower or "kernel" in lower:
        op = "matrix_nullspace"
    elif "column space" in lower or "colspace" in lower:
        op = "matrix_columnspace"
    elif "row space" in lower or "rowspace" in lower:
        op = "matrix_rowspace"
    elif "linearly independent" in lower and (
        "column" in lower or "columns" in lower
    ):
        op = "matrix_independent_columns"
    elif re.search(r"\brank\b", lower):
        op = "matrix_rank"
    if op is None:
        return None

    # Parse two so a compound request cannot silently certify only matrix A.
    matrices = bracket_matrices(cleaned, limit=2)
    if not matrices or len(matrices) != 1:
        return None
    rows = matrices[0]
    if op in {"matrix_eigenvectors", "matrix_diagonalize"} and any(
        len(row) != len(rows) for row in rows
    ):
        return None
    return MathIntent(
        kind="matrix",
        school_op=op,
        matrix_rows=rows,
        operation="solve",
    )


def _extract_two_lists(cleaned: str) -> tuple[list[float], list[float]] | None:
    groups = re.findall(r"\[([^\[\]]+)\]", cleaned)
    if len(groups) != 2:
        return None
    left = numeric_data_values(groups[0])
    right = numeric_data_values(groups[1])
    if left is None or right is None:
        return None
    if len(left) != len(right) or len(left) < 2:
        return None
    return left, right


def _extract_bivariate_statistics_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    op: str | None = None
    if "correlation" in lower or "pearson" in lower:
        op = "correlation"
    elif "covariance" in lower:
        if "sample" in lower:
            op = "sample_covariance"
        else:
            # Match Recall's existing bare-variance convention: population.
            op = "population_covariance"
    elif any(
        cue in lower
        for cue in (
            "linear regression",
            "regression line",
            "line of best fit",
            "least squares line",
        )
    ):
        op = "linear_regression"
    if op is None:
        return None
    pairs = _extract_two_lists(cleaned)
    if pairs is None:
        return None
    x_values, y_values = pairs
    return MathIntent(
        kind="statistics",
        school_op=op,
        vec_a=x_values,
        vec_b=y_values,
        operation="solve",
    )


def _composition_patterns() -> tuple[re.Pattern[str], re.Pattern[str]]:
    suffix = (
        r"(?=\s*(?:,|;)?\s*"
        r"(?:find|compute|evaluate|what\s+is)\b|[?.!]*$)"
    )
    f_then_g = re.compile(
        r"f\s*\(\s*x\s*\)\s*=\s*(.+?)\s*(?:,|;|\band\b)\s*"
        r"g\s*\(\s*x\s*\)\s*=\s*(.+?)" + suffix,
        re.IGNORECASE,
    )
    g_then_f = re.compile(
        r"g\s*\(\s*x\s*\)\s*=\s*(.+?)\s*(?:,|;|\band\b)\s*"
        r"f\s*\(\s*x\s*\)\s*=\s*(.+?)" + suffix,
        re.IGNORECASE,
    )
    return f_then_g, g_then_f


def _extract_function_composition(cleaned: str) -> MathIntent | None:
    compact = re.sub(r"\s+", "", cleaned.lower())
    if "f(g(x))" not in compact and "g(f(x))" not in compact:
        return None

    # Explicit named definitions only. Requiring both assignments prevents us
    # from silently composing a guessed function from surrounding prose.
    found: re.Match[str] | None = None
    reversed_defs = False
    for idx, pattern in enumerate(_composition_patterns()):
        found = pattern.search(cleaned)
        if found is not None:
            reversed_defs = idx == 1
            break
    if found is None:
        return None
    first = _clean_expr(found.group(1))
    second = _clean_expr(found.group(2))
    if first is None or second is None:
        return None
    f_expr, g_expr = (second, first) if reversed_defs else (first, second)
    if "f(g(x))" in compact:
        op = "function_compose_fg"
    else:
        op = "function_compose_gf"
    return MathIntent(
        kind="calculus",
        school_op=op,
        expr=f_expr,
        expr2=g_expr,
        variable="x",
        operation="solve",
    )


def _extract_function_intent(cleaned: str) -> MathIntent | None:
    composed = _extract_function_composition(cleaned)
    if composed is not None:
        return composed

    lower = cleaned.lower()
    for cue, op in (
        ("domain of", "function_domain"),
        ("range of", "function_range"),
        ("inverse function of", "function_inverse"),
        ("inverse of", "function_inverse"),
    ):
        idx = lower.find(cue)
        if idx == -1:
            continue
        if op == "function_inverse" and "[[" in cleaned:
            return None
        if (
            op == "function_inverse"
            and cue == "inverse of"
            and "f(" not in lower[idx:]
        ):
            # Avoid stealing modular, trig, and matrix inverse requests.
            continue
        expr = _clean_expr(cleaned[idx + len(cue) :])
        if expr is not None:
            return MathIntent(
                kind="calculus",
                school_op=op,
                expr=expr,
                variable="x",
                operation="solve",
            )

    if "even or odd" in lower or "odd or even" in lower:
        match = re.search(
            r"(?:f\s*\(\s*x\s*\)|y)\s*=\s*(.+?)"
            r"(?=\s+(?:is\s+)?(?:even|odd)\b|[?.!]*$)",
            cleaned,
            re.IGNORECASE,
        )
        if match is None:
            return None
        expr = _clean_expr(match.group(1))
        if expr is None:
            return None
        return MathIntent(
            kind="calculus",
            school_op="function_even_odd",
            expr=expr,
            variable="x",
            operation="solve",
        )
    return None


def _extract_calculus_application_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    interval = _bounds(cleaned)
    if interval is None:
        return None
    low, high, bounds_at = interval

    area_at = lower.find("area between")
    if area_at != -1 and area_at < bounds_at:
        body = cleaned[area_at + len("area between") : bounds_at].strip(" ,;")
        split = re.split(r"\s+and\s+", body, maxsplit=1, flags=re.IGNORECASE)
        if len(split) != 2:
            return None
        left = _clean_expr(split[0])
        right = _clean_expr(split[1])
        if left is None or right is None:
            return None
        return MathIntent(
            kind="calculus",
            school_op="area_between_curves",
            expr=left,
            expr2=right,
            variable="x",
            integral_lower=low,
            integral_upper=high,
            operation="solve",
        )

    arc_at = lower.find("arc length")
    if arc_at != -1 and arc_at < bounds_at:
        body = cleaned[arc_at + len("arc length") : bounds_at].strip(" ,;")
        if body.lower().startswith("of "):
            body = body[3:].lstrip()
        expr = _clean_expr(body)
        if expr is None:
            return None
        return MathIntent(
            kind="calculus",
            school_op="arc_length",
            expr=expr,
            variable="x",
            integral_lower=low,
            integral_upper=high,
            operation="solve",
        )

    volume_words = ("revolution", "revolved", "rotated")
    if "volume" in lower and any(word in lower for word in volume_words):
        axis: str | None = None
        if "x-axis" in lower or "x axis" in lower:
            axis = "x"
        elif "y-axis" in lower or "y axis" in lower:
            axis = "y"
        if axis is None:
            return None
        # Accept the common school phrasing: "volume of revolution of y=f(x)
        # from a to b about the x-axis". Text after bounds is ignored only
        # after the axis itself has been recognized.
        start = lower.find("of ", lower.find("volume"))
        if start == -1 or start >= bounds_at:
            return None
        body = cleaned[start + 3 : bounds_at].strip(" ,;")
        if body.lower().startswith("revolution of "):
            body = body[len("revolution of ") :].lstrip()
        expr = _clean_expr(body)
        if expr is None:
            return None
        return MathIntent(
            kind="calculus",
            school_op=f"volume_revolution_{axis}",
            expr=expr,
            variable="x",
            integral_lower=low,
            integral_upper=high,
            operation="solve",
        )
    return None


ADVANCED_EXTRACTORS = (
    _extract_advanced_matrix_intent,
    _extract_bivariate_statistics_intent,
    _extract_function_intent,
    _extract_calculus_application_intent,
)
