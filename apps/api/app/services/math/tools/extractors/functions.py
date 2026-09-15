"""Function-analysis intent extraction for verified undergraduate homework."""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
from app.services.math.tools.helpers import (
    _normalize_latex_expr,
    _strip_trailing_filler,
    math_expr_or_none,
)

_FUNCTION_DEF_RE = re.compile(r"\b([fgh])\s*\(\s*([a-zA-Z])\s*\)\s*=", re.IGNORECASE)
_TRAILING_CONNECTOR_RE = re.compile(r"(?:,|;|\band)\s*$", re.IGNORECASE)


def _function_definitions(text: str) -> dict[str, tuple[str, str]]:
    """Extract simple ``f(x)=...`` definitions without parsing prose as math."""
    matches = list(_FUNCTION_DEF_RE.finditer(text))
    found: dict[str, tuple[str, str]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw = text[match.end() : end].strip()
        raw = _TRAILING_CONNECTOR_RE.sub("", raw).strip()
        raw = _strip_trailing_filler(raw)
        expr = math_expr_or_none(_normalize_latex_expr(raw))
        if expr is not None:
            found[match.group(1).lower()] = (match.group(2), expr)
    return found


def _expression_after(text: str, phrase: str) -> tuple[str, str] | None:
    lower = text.lower()
    idx = lower.find(phrase)
    if idx == -1:
        return None
    raw = _strip_trailing_filler(text[idx + len(phrase) :].strip())
    low = raw.lower()
    for prefix in ("the function ", "function "):
        if low.startswith(prefix):
            raw = raw[len(prefix) :].strip()
            break
    expr = math_expr_or_none(_normalize_latex_expr(raw))
    if expr is None:
        return None
    from app.services.math.solve import guess_variables

    variables = guess_variables(expr)
    return expr, variables[0] if len(variables) == 1 else "x"


def _extract_function_analysis_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    defs = _function_definitions(cleaned)

    compact = re.sub(r"\s+", "", lower)
    composition_requested = (
        "compose" in lower
        or "composition" in lower
        or "f(g(" in compact
        or "g(f(" in compact
    )
    if composition_requested and len(defs) >= 2:
        if "g(f(" in compact:
            outer_name, inner_name = "g", "f"
        else:
            outer_name, inner_name = "f", "g"
        if outer_name not in defs or inner_name not in defs:
            return None
        outer_var, outer_expr = defs[outer_name]
        inner_var, inner_expr = defs[inner_name]
        if outer_var != inner_var:
            return None
        return MathIntent(
            kind="calculus",
            operation="simplify",
            school_op="function_composition",
            expr=outer_expr,
            expr2=inner_expr,
            variable=outer_var,
        )

    feature: str | None = None
    if "domain of" in lower or "find domain" in lower:
        feature = "domain"
    elif "range of" in lower or "find range" in lower:
        feature = "range"
    elif (
        "inverse function" in lower
        or "inverse of f(" in lower
        or "inverse of g(" in lower
        or "f^-1" in compact
        or "f^{-1}" in compact
    ):
        feature = "inverse"
    if feature is None:
        return None

    if defs:
        name = "f"
        if "of g(" in lower and "g" in defs:
            name = "g"
        if name not in defs:
            name = next(iter(defs))
        variable, expr = defs[name]
    else:
        if feature == "domain":
            phrase = "domain of"
        elif feature == "range":
            phrase = "range of"
        else:
            phrase = "inverse of"
        hit = _expression_after(cleaned, phrase)
        if hit is None:
            return None
        expr, variable = hit

    return MathIntent(
        kind="calculus",
        operation="simplify",
        school_op=f"function_{feature}",
        expr=expr,
        variable=variable,
    )


FUNCTION_EXTRACTORS = (_extract_function_analysis_intent,)
