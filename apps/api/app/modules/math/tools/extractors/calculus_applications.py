"""Intent extraction for area between curves, arc length, and volume.

Strict on purpose. These questions were refused outright at the funnel after an
area question was answered with its curves' *intersection points*; a partial
parse here would reopen exactly that hole, because a verified block tells the
model not to recompute. Every operand — both curves, both bounds, the axis —
has to be explicit or the request falls through unclaimed.
"""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
from app.modules.math.tools.helpers import (
    _normalize_latex_expr,
    _strip_trailing_filler,
    math_expr_or_none,
    peel_function_definition,
)

# A bound may be a number, a fraction, pi, or e — the values school questions
# actually use. Anything else is left unclaimed rather than guessed at.
# Ordered longest-first, and closed with a lookahead, because a *partial* bound
# match silently shortens the interval instead of failing. "from 0 to 2*pi"
# matched just the "2" and answered the area on [0, 2] as though it were the
# area on [0, 2*pi] - a wrong number that looks entirely plausible.
_BOUND = (
    r"[-+]?(?:"
    r"\d+(?:\.\d+)?\s*\*\s*(?:pi|π|e)"
    r"|\d+(?:\.\d+)?\s*(?:pi|π)"
    r"|(?:pi|π|e)\s*/\s*\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?"
    r"|pi|π|e"
    r"|\d+(?:\.\d+)?|\.\d+"
    r")(?![\w.*])"
)
_FROM_TO_RE = re.compile(
    rf"\bfrom\s+(?:x\s*=\s*)?({_BOUND})\s+to\s+(?:x\s*=\s*)?({_BOUND})\b", re.IGNORECASE
)
_ON_INTERVAL_RE = re.compile(
    rf"\b(?:on|over)\s*\[\s*({_BOUND})\s*,\s*({_BOUND})\s*\]", re.IGNORECASE
)
_BETWEEN_BOUNDS_RE = re.compile(
    rf"\bbetween\s+x\s*=\s*({_BOUND})\s+and\s+x\s*=\s*({_BOUND})\b", re.IGNORECASE
)


def _clean(raw: str) -> str | None:
    text = peel_function_definition(_strip_trailing_filler(raw.strip(" ,;")))
    while text and text[-1] in ".?!":
        text = text[:-1].rstrip()
    return math_expr_or_none(_normalize_latex_expr(text))


def _bounds(cleaned: str) -> tuple[str, str, int] | None:
    for pattern in (_FROM_TO_RE, _ON_INTERVAL_RE, _BETWEEN_BOUNDS_RE):
        match = pattern.search(cleaned)
        if match is not None:
            return (
                match.group(1).replace("π", "pi"),
                match.group(2).replace("π", "pi"),
                match.start(),
            )
    return None


def _extract_area_between_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    at = lower.find("area between")
    if at == -1:
        return None
    interval = _bounds(cleaned)
    if interval is None:
        return None
    low, high, bounds_at = interval
    if bounds_at <= at:
        return None

    body = cleaned[at + len("area between") : bounds_at].strip(" ,;")
    body = re.sub(r"^(?:the\s+)?curves\s+", "", body, flags=re.IGNORECASE)
    halves = re.split(r"\s+and\s+", body, maxsplit=1, flags=re.IGNORECASE)
    if len(halves) != 2:
        return None
    first = _clean(halves[0])
    second = _clean(halves[1])
    if first is None or second is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="solve",
        school_op="area_between_curves",
        expr=first,
        expr2=second,
        variable="x",
        integral_lower=low,
        integral_upper=high,
    )


def _extract_arc_length_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    at = lower.find("arc length")
    if at == -1:
        return None
    interval = _bounds(cleaned)
    if interval is None:
        return None
    low, high, bounds_at = interval
    if bounds_at <= at:
        return None

    body = cleaned[at + len("arc length") : bounds_at].strip(" ,;")
    body = re.sub(r"^of\s+", "", body, flags=re.IGNORECASE)
    expr = _clean(body)
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="solve",
        school_op="arc_length",
        expr=expr,
        variable="x",
        integral_lower=low,
        integral_upper=high,
    )


_REVOLVE_RE = re.compile(r"\b(?:revolution|revolved|rotated|revolving|rotating)\b", re.IGNORECASE)


def _extract_volume_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "volume" not in lower or _REVOLVE_RE.search(cleaned) is None:
        return None
    interval = _bounds(cleaned)
    if interval is None:
        return None
    low, high, bounds_at = interval

    # The axis decides the formula — disks about x, shells about y — so an
    # unnamed axis is refused rather than assumed to be x.
    if re.search(r"\bx[- ]axis\b", lower):
        axis = "x"
    elif re.search(r"\by[- ]axis\b", lower):
        axis = "y"
    else:
        return None

    start = lower.find("of ", lower.find("volume"))
    if start == -1 or start >= bounds_at:
        return None
    body = cleaned[start + 3 : bounds_at].strip(" ,;")
    body = re.sub(
        r"^(?:revolution|the\s+region)\s+(?:of|under|bounded\s+by)\s+",
        "",
        body,
        flags=re.IGNORECASE,
    )
    expr = _clean(body)
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="solve",
        school_op=f"volume_revolution_{axis}",
        expr=expr,
        variable="x",
        integral_lower=low,
        integral_upper=high,
    )


CALCULUS_APPLICATION_EXTRACTORS = (
    _extract_area_between_intent,
    _extract_arc_length_intent,
    _extract_volume_intent,
)
