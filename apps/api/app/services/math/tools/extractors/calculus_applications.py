"""Strict extractors for common single-variable calculus applications."""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
from app.services.math.tools.helpers import (
    _normalize_latex_expr,
    _strip_trailing_filler,
    math_expr_or_none,
    peel_function_definition,
)

_NAMED_BOUNDS_RE = re.compile(
    r"\bfrom\s+([a-zA-Z])\s*=\s*([^\s,;]+)\s+to\s+([^\s,;]+)",
    re.IGNORECASE,
)


def _function_expression(raw: str) -> str | None:
    value = _strip_trailing_filler(raw.strip())
    if value.lower().startswith("y="):
        value = value[2:].strip()
    elif value.lower().startswith("y ="):
        value = value[3:].strip()
    value = peel_function_definition(value)
    return math_expr_or_none(_normalize_latex_expr(value))


def _bounds(cleaned: str) -> tuple[re.Match[str], str, str, str] | None:
    hit = _NAMED_BOUNDS_RE.search(cleaned)
    if hit is None:
        return None
    variable = hit.group(1)
    lower = math_expr_or_none(_normalize_latex_expr(hit.group(2)))
    upper = math_expr_or_none(_normalize_latex_expr(hit.group(3).rstrip(".?!")))
    if lower is None or upper is None:
        return None
    return hit, variable, lower, upper


def _extract_area_between_curves_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    phrase = "area between"
    start = lower.find(phrase)
    bound_data = _bounds(cleaned)
    if start == -1 or bound_data is None:
        return None
    hit, variable, lo, hi = bound_data
    body = cleaned[start + len(phrase) : hit.start()].strip()
    split = body.lower().find(" and ")
    if split == -1:
        return None
    expr1 = _function_expression(body[:split])
    expr2 = _function_expression(body[split + 5 :])
    if expr1 is None or expr2 is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="integrate",
        school_op="area_between_curves",
        expr=expr1,
        expr2=expr2,
        variable=variable,
        integral_lower=lo,
        integral_upper=hi,
    )


def _extract_arc_length_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    start = lower.find("arc length")
    bound_data = _bounds(cleaned)
    if start == -1 or bound_data is None:
        return None
    hit, variable, lo, hi = bound_data
    body = cleaned[start + len("arc length") : hit.start()].strip()
    if body.lower().startswith("of "):
        body = body[3:].strip()
    expr = _function_expression(body)
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="integrate",
        school_op="arc_length",
        expr=expr,
        variable=variable,
        integral_lower=lo,
        integral_upper=hi,
    )


def _extract_volume_revolution_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "volume" not in lower or not any(word in lower for word in ("revolution", "revolved")):
        return None
    # This first verified template is the disk/washer case around the x-axis.
    # Do not silently apply it to the y-axis or an arbitrary line.
    if "x-axis" not in lower and "x axis" not in lower:
        return None
    bound_data = _bounds(cleaned)
    if bound_data is None:
        return None
    hit, variable, lo, hi = bound_data
    prefix = cleaned[: hit.start()].strip()
    of_at = prefix.lower().rfind(" of ")
    if of_at == -1:
        return None
    expr = _function_expression(prefix[of_at + 4 :])
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="integrate",
        school_op="volume_revolution_x",
        expr=expr,
        variable=variable,
        integral_lower=lo,
        integral_upper=hi,
    )


CALCULUS_APPLICATION_EXTRACTORS = (
    _extract_area_between_curves_intent,
    _extract_arc_length_intent,
    _extract_volume_revolution_intent,
)


def calculus_application_requested(text: str) -> bool:
    """True when the user asked for one of these applications, supported or not."""
    lower = text.lower()
    return (
        "area between" in lower
        or "arc length" in lower
        or ("volume" in lower and any(word in lower for word in ("revolution", "revolved")))
    )


def extract_calculus_application_intent(cleaned: str) -> MathIntent | None:
    """Try the supported templates; callers must refuse fall-through on None."""
    for extractor in CALCULUS_APPLICATION_EXTRACTORS:
        intent = extractor(cleaned)
        if intent is not None:
            return intent
    return None
