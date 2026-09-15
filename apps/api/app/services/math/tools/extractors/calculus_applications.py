"""Strict extraction for verified calculus applications."""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
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
    value = _strip_trailing_filler(raw.strip(" ,;"))
    value = peel_function_definition(value)
    while value and value[-1] in ".?!":
        value = value[:-1].rstrip()
    return math_expr_or_none(value)


def _bounds(text: str) -> tuple[str, str, int] | None:
    match = _FROM_TO_RE.search(text) or _ON_INTERVAL_RE.search(text)
    if match is None:
        return None
    lower = match.group(1).replace("π", "pi")
    upper = match.group(2).replace("π", "pi")
    return lower, upper, match.start()


def calculus_application_requested(text: str) -> bool:
    lower = text.lower()
    return (
        "area between" in lower
        or "arc length" in lower
        or (
            "volume" in lower
            and any(word in lower for word in ("revolution", "revolved", "rotated"))
        )
    )


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
            operation="integrate",
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
            operation="integrate",
        )

    if "volume" in lower and any(word in lower for word in ("revolution", "revolved", "rotated")):
        if "x-axis" in lower or "x axis" in lower:
            axis = "x"
        elif "y-axis" in lower or "y axis" in lower:
            axis = "y"
        else:
            return None
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
            operation="integrate",
        )

    return None


CALCULUS_APPLICATION_EXTRACTORS = (_extract_calculus_application_intent,)
