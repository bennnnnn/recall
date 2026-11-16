"""Intent extraction for area between curves, arc length, and volume.

Strict on purpose. These questions were refused outright at the funnel after an
area question was answered with its curves' *intersection points*; a partial
parse here would reopen exactly that hole, because a verified block tells the
model not to recompute. Every operand — both curves, both bounds, the axis —
has to be explicit or the request falls through unclaimed.
"""

from __future__ import annotations

import re

from app.modules.math.schemas import MathIntent
from app.modules.math.solve.declines import sympy_decline
from app.modules.math.tools.expr_rewrite import _normalize_latex_expr, math_expr_or_none
from app.modules.math.tools.function_def import peel_function_definition
from app.modules.math.tools.request_text import strip_trailing_filler
from app.services.glyphs import fold_operator_glyphs

# A bound may be a number, a fraction, pi, or e — the values school questions
# actually use ("7π/4", "1/e", "e^2" included). Anything else is left unclaimed rather
# than guessed at.
# Ordered longest-first, and closed with a lookahead, because a *partial* bound
# match silently shortens the interval instead of failing. "from 0 to 2*pi"
# matched just the "2" and answered the area on [0, 2] as though it were the
# area on [0, 2*pi] - a wrong number that looks entirely plausible.
_BOUND = (
    r"[-+]?(?:"
    r"\d+(?:\.\d+)?\s*(?:\*\s*)?(?:pi|π)\s*/\s*\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*\*\s*(?:pi|π|e)"
    r"|\d+(?:\.\d+)?\s*(?:pi|π)"
    r"|(?:pi|π|e)\s*/\s*\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*/\s*(?:pi|π|e)"
    r"|e\s*\^\s*\d+"
    r"|\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?"
    r"|pi|π|e"
    r"|\d+(?:\.\d+)?|\.\d+"
    # Reject a partial bound (``3`` from ``3.5``, ``7π`` from ``7π/4``, ``e`` from
    # ``e^2``), but allow the ordinary sentence-ending period after a complete bound
    # (``to x=3.``).
    r")(?![\w*/^]|\.\d)"
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
_CHAIN_BOUNDS_RE = re.compile(
    rf"({_BOUND})\s*(?:<=|≤|<)\s*x\s*(?:<=|≤|<)\s*({_BOUND})", re.IGNORECASE
)
# "the x-axis and the lines x = -1/2 and x = 3": the vertical lines that close the region.
_LINES_BOUNDS_RE = re.compile(
    rf"(?:\band\s+)?\bthe\s+lines\s+x\s*=\s*({_BOUND})\s+and\s+x\s*=\s*({_BOUND})\b",
    re.IGNORECASE,
)
# An interval the question states, whatever its bounds are written in: "from x = 1/e to",
# "between x = a and", "the lines x = …", "on [": read strictly by ``_bounds`` or not at all.
_STATED_INTERVAL_RE = re.compile(
    r"\bfrom\s+x\s*=|\bbetween\s+x\s*=|\blines\s+x\s*=|\b(?:on|over)\s*\[|"
    r"(?:<=|≤|<)\s*x\s*(?:<=|≤|<)",
    re.IGNORECASE,
)


def _clean(raw: str) -> str | None:
    text = peel_function_definition(strip_trailing_filler(raw.strip(" ,;")))
    while text and text[-1] in ".?!":
        text = text[:-1].rstrip()
    return math_expr_or_none(_normalize_latex_expr(text))


def _bounds(cleaned: str, after: int = 0, before: int | None = None) -> tuple[str, str, int] | None:
    """The first interval stated at or after ``after`` (and ending by ``before``): its bounds
    and where it starts.

    A minus typed as the minus sign (U+2212) or a dash is a minus: "from x = -4 to x = 3"
    is [-4, 3] in any of them (2026-11-16: the sign's form left the question unread, and
    the reply answered the area between the roots). The glyph table maps one character to
    one, so positions stay.
    """
    folded = fold_operator_glyphs(cleaned)
    found = [
        match
        for pattern in (
            _FROM_TO_RE,
            _ON_INTERVAL_RE,
            _BETWEEN_BOUNDS_RE,
            _CHAIN_BOUNDS_RE,
            _LINES_BOUNDS_RE,
        )
        if (match := pattern.search(folded, after, len(folded) if before is None else before))
        is not None
    ]
    if not found:
        return None
    match = min(found, key=lambda match: match.start())
    return (
        match.group(1).replace("π", "pi"),
        match.group(2).replace("π", "pi"),
        match.start(),
    )


# "the area of the region bounded by", "the area enclosed between": the region is the area's.
_OF_REGION = r"(?:of\s+the\s+region\s+)?"
_AREA_BETWEEN_RE = re.compile(
    rf"\barea\s+{_OF_REGION}(?:between|enclosed\s+(?:by|between)|bounded\s+by)\s+",
    re.IGNORECASE,
)
# What names a curve before its formula: "the graph of", "the curves", "the line".
_CURVE_NAME = re.compile(r"^(?:the\s+)?(?:graphs?|curves?|lines?)\s+(?:of\s+)?", re.IGNORECASE)
# A sentence's end: a stop and a space ("… = 3x. Show the curves"), not a decimal point.
_SENTENCE_END = re.compile(r"[.?!](?=\s|$)")


def _curve(raw: str) -> str | None:
    """One curve of a region, as an expression in x; the x-axis is y = 0."""
    named = _CURVE_NAME.sub("", raw.strip())
    if re.fullmatch(r"(?:the\s+)?x[- ]axis", named.strip(), re.IGNORECASE):
        return "0"
    return _clean(named)


def _lead_sentence(cleaned: str, lead: re.Match[str]) -> tuple[int, int]:
    """Where the sentence that asks the area starts and ends. Its interval is the area's;
    one in another sentence is a picture's or another question's ("… and g(x) = 3x. Draw
    the graph from x = -5 to x = 3." integrated over [-5, 3], 109/3 for 125/6)."""
    start = max(
        (stop.end() for stop in _SENTENCE_END.finditer(cleaned, 0, lead.start())), default=0
    )
    stop = _SENTENCE_END.search(cleaned, lead.end())
    return start, stop.start() if stop is not None else len(cleaned)


def _extract_area_between_intent(cleaned: str) -> MathIntent | None:
    lead = _AREA_BETWEEN_RE.search(cleaned)
    if lead is None:
        return None
    start, stop = _lead_sentence(cleaned, lead)
    interval = _bounds(cleaned, lead.end(), stop)
    end = interval[2] if interval is not None else stop
    body = cleaned[lead.end() : end].strip(" ,;.?!")
    halves = re.split(r"\s*,?\s+and\s+", _CURVE_NAME.sub("", body), maxsplit=1, flags=re.I)
    if len(halves) != 2:
        return None
    first, second = _curve(halves[0]), _curve(halves[1])
    if first is None or second is None:
        return None
    if interval is None:
        # The stated interval wins: one its sentence writes in a form the bounds do not
        # read ("from x = 1/e² to …") is never replaced by where the curves meet.
        if _STATED_INTERVAL_RE.search(fold_operator_glyphs(cleaned), start, stop):
            return None
        # No interval stated: the region the curves enclose runs between where they meet.
        meeting = _meeting_points(first, second)
        if meeting is None:
            return None
        low, high = meeting
    else:
        low, high, _ = interval
    return MathIntent(
        kind="calculus",
        operation="solve",
        school_op="area_between_curves",
        expr=first,
        expr2=second,
        variable="x",
        integral_lower=low,
        integral_upper=high,
        trial_outcome="meeting points" if interval is None else None,
    )


def _meeting_points(first: str, second: str) -> tuple[str, str] | None:
    """The outermost real crossings, when the curves cross at two or more points.

    One crossing (y = x and y = 2x) or infinitely many (y = sin x and y = 0)
    encloses no single region, so the question stays unclaimed.
    """
    from sympy import Eq, FiniteSet, S, Symbol, solveset, sstr

    from app.modules.math import solve as math_solve

    x = Symbol("x", real=True)
    with sympy_decline() as declined:
        f = math_solve.parse_expression(first, ["x"], real=True)
        g = math_solve.parse_expression(second, ["x"], real=True)
        roots = solveset(Eq(f, g), x, domain=S.Reals)
    if declined:
        return None
    if not isinstance(roots, FiniteSet):
        return None
    real = sorted((root for root in roots if root.is_real), key=lambda root: float(root))
    if len(real) < 2:
        return None
    return sstr(real[0]), sstr(real[-1])


_AREA_UNDER_RE = re.compile(
    r"\barea\s+(?:under|below|beneath)\s+(?:the\s+(?:curve|graph)\s+(?:of\s+)?)?"
    rf"|\barea\s+{_OF_REGION}(?:bounded|enclosed)\s+by\s+(?:the\s+(?:curve|graph)\s+(?:of\s+)?)?",
    re.IGNORECASE,
)
_X_AXIS_RE = re.compile(r",?\s*(?:and\s+)?the\s+x[- ]axis\b,?", re.IGNORECASE)


def _extract_area_under_intent(cleaned: str) -> MathIntent | None:
    """``area under y = x^2 between x = 1 and x = 2``: the area between the curve and y = 0.

    The area-between solver already takes the curve's absolute value, so a
    stretch below the x-axis counts as area, not as a negative.
    """
    lead = _AREA_UNDER_RE.search(cleaned)
    if lead is None:
        return None
    interval = _bounds(cleaned, lead.end(), _lead_sentence(cleaned, lead)[1])
    if interval is None:
        return None
    low, high, bounds_at = interval
    body = _X_AXIS_RE.sub("", cleaned[lead.end() : bounds_at]).strip(" ,;")
    curve = _clean(body)
    if curve is None or "=" in curve:
        return None
    return MathIntent(
        kind="calculus",
        operation="solve",
        school_op="area_between_curves",
        expr=curve,
        expr2="0",
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
    offset = 3
    if start == -1:
        start = lower.find("when ", lower.find("volume"))
        offset = len("when ")
    if start == -1 or start >= bounds_at:
        return None
    body = cleaned[start + offset : bounds_at].strip(" ,;")
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


def _extract_curve_point_intent(cleaned: str) -> MathIntent | None:
    from app.modules.math.tools.school.curve_points import extract_curve_point_intent

    return extract_curve_point_intent(cleaned)


CALCULUS_APPLICATION_EXTRACTORS = (
    # Tangent/normal lines and stationary points: read as algebra, the curve
    # and the point became a system to solve.
    _extract_curve_point_intent,
    _extract_area_between_intent,
    _extract_area_under_intent,
    _extract_arc_length_intent,
    _extract_volume_intent,
)
