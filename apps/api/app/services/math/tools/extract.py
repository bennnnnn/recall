"""Ordered MathIntent extraction behind the stable public seam."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from app.models.schemas.math import MathIntent
from app.services.math.tools.extractors.algebra import (
    ALGEBRA_EXTRACTORS,
    PRE_DISCRETE_ALGEBRA_EXTRACTORS,
)
from app.services.math.tools.extractors.calculus import CALCULUS_EXTRACTORS
from app.services.math.tools.extractors.discrete_statistics import (
    DISCRETE_STATISTICS_EXTRACTORS,
)
from app.services.math.tools.extractors.geometry_graph import (
    GEOMETRY_GRAPH_EXTRACTORS,
    SOLID_EXTRACTOR,
)
from app.services.math.tools.helpers import has_assignment_evaluation_request, math_expr_or_none
from app.services.math.tools.school import SCHOOL_EXTRACTORS
from app.services.physics.extract import PHYSICS_EXTRACTORS

_INTENT_EXTRACTORS: Sequence[Callable[[str], MathIntent | None]] = (
    SOLID_EXTRACTOR,
    *SCHOOL_EXTRACTORS,
    *PHYSICS_EXTRACTORS,
    *GEOMETRY_GRAPH_EXTRACTORS,
    *CALCULUS_EXTRACTORS,
    *PRE_DISCRETE_ALGEBRA_EXTRACTORS,
    *DISCRETE_STATISTICS_EXTRACTORS,
    *ALGEBRA_EXTRACTORS,
)

_ROOTS_RE = re.compile(r"\b(?:find(?:\s+the)?\s+)?(?:roots|zeros)\s+of\s+(.+)", re.IGNORECASE)
_TRIG_FUNCTION_RE = re.compile(r"\b(?:sin|cos|tan|cot|sec|csc)\s*\(", re.IGNORECASE)
_RESTRICTED_TRIG_DOMAIN_RE = re.compile(
    r"[<>\u2264\u2265\u2208\u2102\u2124\u2115\u211a\[\]]"
    r"|\\in\b|\\mathbb\s*\{[CZNQ]\}"
    r"|\b(?:complex|imaginary|integers?|naturals?|rationals?|irrationals?|"
    r"positive|negative|nonnegative|nonpositive|degrees?)\b"
    r"|\bin\s*(?:\(|[CZNQ]\b)",
    re.IGNORECASE,
)
_INTERVAL_BOUND = (
    r"[-+]?\s*(?:\d+(?:\.\d+)?|\.\d+|pi|π|\\pi|oo|infinity|∞)"
    r"(?:\s*[*/]\s*(?:\d+(?:\.\d+)?|pi|π|\\pi))*"
)
_TRIG_INTERVAL_RE = re.compile(
    rf"\bfrom\s+{_INTERVAL_BOUND}\s+to\s+{_INTERVAL_BOUND}"
    rf"|\bbetween\s+{_INTERVAL_BOUND}\s+and\s+{_INTERVAL_BOUND}"
    r"|\bwithin\s+(?:the\s+)?interval\b",
    re.IGNORECASE,
)


def trig_domain_would_be_dropped(expression: str, text: str) -> bool:
    """The trig solver owns all real values, not an interval or another domain.

    Equation extraction peels surrounding prose. Do not silently drop a
    user-specified domain and certify an all-real answer in its place.
    Explicit real-domain wording remains supported.
    """
    return bool(
        _TRIG_FUNCTION_RE.search(expression)
        and (_RESTRICTED_TRIG_DOMAIN_RE.search(text) or _TRIG_INTERVAL_RE.search(text))
    )


def extract_math_intent(text: str) -> MathIntent | None:
    from app.services.math import match as mtm

    cleaned = mtm.prepare(text)
    if not cleaned:
        return None
    roots_match = _ROOTS_RE.search(cleaned)
    if roots_match:
        tail = math_expr_or_none(roots_match.group(1))
        if tail is not None and "=" not in tail:
            cleaned = f"solve {tail} = 0"
    for extractor in _INTENT_EXTRACTORS:
        intent = extractor(cleaned)
        if intent is not None:
            # Successful substitution arithmetic wins earlier. If that did
            # not parse, never certify just the given assignment(s) while
            # silently ignoring the requested evaluation.
            if intent.kind in {"equation", "system"} and has_assignment_evaluation_request(text):
                return None
            if intent.kind == "equation" and trig_domain_would_be_dropped(
                f"{intent.lhs or ''} {intent.rhs or ''}", text
            ):
                return None
            if intent.kind in {
                "rectangle",
                "square",
                "triangle",
                "right_triangle",
                "triangle_sides",
                "circle",
                "trapezoid",
                "parallelogram",
                "sector",
            }:
                # A natural-language measurement must not inherit the public
                # structured-input schema's legacy centimetre default. AAA
                # triangles already carry relative side lengths in generic units.
                from app.services.math.match.units import solid_length_unit

                if intent.kind != "triangle_sides" or intent.unit != "units":
                    unit = solid_length_unit(cleaned)
                    if unit is None:
                        return None
                    intent = intent.model_copy(update={"unit": unit})
            return intent
    return None


_GRAPH_FOLLOWUP_VERBS = ("graph", "plot", "sketch", "draw", "visualize", "visualise", "chart")
_GRAPH_FOLLOWUP_OBJECTS = frozenset(
    {
        "",
        "it",
        "this",
        "that",
        "the equation",
        "the function",
        "the curve",
        "the parabola",
        "the quadratic",
        "the polynomial",
        "this equation",
        "that equation",
        "this function",
        "that function",
    }
)
_POLITE_PREFIXES = ("please ", "can you ", "could you ")


def _strip_polite_wrappers(lower: str) -> str:
    s = lower
    changed = True
    while changed:
        changed = False
        if s.startswith("please "):
            s = s[7:].strip()
            changed = True
        if s.endswith(" please"):
            s = s[:-7].strip()
            changed = True
        for prefix in _POLITE_PREFIXES:
            if s.startswith(prefix):
                s = s[len(prefix) :].strip()
                changed = True
                break
    return s


def is_graph_followup(text: str) -> bool:
    """True for ``graph it`` / ``plot this equation`` with no new formula."""
    from app.services.math.match.scan import prepare

    cleaned = prepare(text)
    if not cleaned:
        return False
    lower = _strip_polite_wrappers(cleaned.lower().rstrip(".!?"))
    rest: str | None = None
    for verb in _GRAPH_FOLLOWUP_VERBS:
        if lower == verb:
            rest = ""
            break
        prefix = f"{verb} "
        if lower.startswith(prefix):
            rest = lower[len(prefix) :].strip()
            break
    if rest is None:
        return False
    return rest in _GRAPH_FOLLOWUP_OBJECTS


def _is_plottable_expr(expr: str) -> bool:
    compact = expr.replace(" ", "")
    if not compact:
        return False
    lower = compact.lower()
    if lower in {"it", "this", "that"}:
        return False
    from app.services.math.match.scan import has_unknown_english_run

    if has_unknown_english_run(compact):
        return False
    return any(ch.isdigit() for ch in compact) or "x" in lower


def _plottable_graph_source(text: str) -> str | None:
    intent = extract_math_intent(text)
    if intent is None:
        return None
    if intent.kind == "graph" and intent.expr and _is_plottable_expr(intent.expr):
        return intent.expr
    if intent.kind == "graph_pair" and intent.expr and intent.expr2:
        if _is_plottable_expr(intent.expr) and _is_plottable_expr(intent.expr2):
            return f"{intent.expr} and {intent.expr2}"
    if intent.kind == "vertical" and intent.point_x is not None:
        return f"x={intent.point_x:g}"
    if intent.kind == "equation" and intent.lhs and intent.rhs:
        if _is_plottable_expr(intent.lhs) or _is_plottable_expr(intent.rhs):
            return f"{intent.lhs}={intent.rhs}"
    return None


def resolve_graph_followup(text: str, prior_user_messages: list[str] | None) -> tuple[str, bool]:
    """Rewrite ``graph it`` from a prior equation.

    Returns ``(content, skip_math)``. ``skip_math`` is True only when this
    *is* a pronoun follow-up with no plottable prior — caller must not stamp
    *Couldn't verify* (``graph_expr("it")`` looks like math and used to).
    """
    if not is_graph_followup(text):
        return text, False
    for prior in reversed(prior_user_messages or []):
        src = _plottable_graph_source(prior)
        if src:
            return f"graph {src}", False
    return text, True
