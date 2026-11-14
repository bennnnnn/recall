"""The operations a question asks for: a derivative (its order, at a point or not), an
integral, a limit, or how a function behaves (its extreme values, where it rises and falls,
its asymptotes and intercepts).

A computation answers the question only when it computes what the question asks
(``computes_the_ask``); any other is a step of the working. The equation solver read
"Find dy/dx for y = x ln x" as the equation y = x ln x and certified x = e^{W(y)} as the
derivative, and the model's own readings and SymPy calls held the user's formula but not
the question: f'(x) = 2x - 1 was the checked card for lim_{h->0} (f(3 + h) - f(3))/h
(asked: 5), the first derivative for d^2y/dx^2, and f'(x) for an absolute maximum and
minimum (2026-11-14, grade 12 book). The words read here are the readers' own: the
derivative notation and verbs of ``calc_op``, the limit and integral signs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.math.match.calculus import lagrange_prime_run, skip_optional_paren_var
from app.modules.math.match.scan import CALC_OP, CALC_OP_SPELLINGS, ddx_cue_at
from app.modules.math.schemas import MathIntent
from app.modules.turn_reading.at_a_point import asks_at_a_point

_MAX_TEXT = 2000
# d^2y/dx^2 and d²y/dx²: a derivative of the order its exponent names.
_HIGHER_LEIBNIZ = re.compile(
    r"\bd\s*(?:\^\s*\{?([2-4])\}?|([²³⁴]))\s*(?:[a-zA-Z]\s*)?/\s*"
    r"d\s*[a-zA-Z]\s*(?:\^\s*\{?[2-4]|[²³⁴])",
    re.IGNORECASE,
)
_SUPERSCRIPT_ORDERS = {"²": 2, "³": 3, "⁴": 4}
_ORDINAL_DERIVATIVE = re.compile(
    r"\b(second|2nd|third|3rd|fourth|4th)[\s-]+(?:order\s+)?deriv", re.IGNORECASE
)
_ORDINALS = {"second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4}
# The instantaneous rate of one letter in another is its derivative: "the rate of change of
# y with respect to x". An average rate is a difference quotient over an interval.
RATE_OF_CHANGE = re.compile(
    r"(?<!average\s)\brate\s+of\s+change\s+of\s+[a-zA-Z]\s+with\s+respect\s+to\s+[a-zA-Z]\b",
    re.IGNORECASE,
)
_LIMIT = re.compile(r"\blim(?:its?)?(?![a-z])", re.IGNORECASE)
_ANTIDERIVATIVE = re.compile(r"\banti-?deriv", re.IGNORECASE)
# How a function behaves, which a derivative or a rewrite is only a step to: its extreme
# values, where it rises, falls and bends, its asymptotes and intercepts.
_BEHAVIOUR = re.compile(
    r"\b(?:maxim(?:um|a|i[sz]e)|minim(?:um|a|i[sz]e)|extrem(?:um|a|e\s+values?)"
    r"|(?:local|absolute|relative|global)\s+(?:max|min)"
    r"|critical\s+(?:numbers?|points?|values?)|(?:stationary|turning)\s+points?"
    r"|inflections?|(?:points?\s+of\s+)?inflexion|concav(?:e|ity)|increasing|decreasing"
    r"|monoton(?:e|ic|icity)|asymptotes?|intercepts?)\b",
    re.IGNORECASE,
)
# Of those, the extreme values themselves: where the function turns is a step to them.
_EXTREME_VALUES = re.compile(
    r"\b(?:maxim(?:um|a)|minim(?:um|a)|extrem(?:um|a|e\s+values?)"
    r"|(?:local|absolute|relative|global)\s+(?:max|min))\b",
    re.IGNORECASE,
)
# The greatest and the least, each: "the local maximum and minimum values".
_MAXIMUM = re.compile(r"\b(?:maxim(?:um|a)|greatest|largest|highest)\b", re.IGNORECASE)
_MINIMUM = re.compile(r"\b(?:minim(?:um|a)|least|smallest|lowest)\b", re.IGNORECASE)
_DERIVATIVE_WORDS = frozenset({"differentiate", "derivative"})
_INTEGRAL_WORDS = frozenset({"integrate", "integral"})
Computation = Literal["solve", "derivative", "integral", "limit", "rewrite"]


@dataclass(frozen=True)
class AskedOperations:
    """What a question asks to be computed."""

    derivative_orders: frozenset[int] = frozenset()
    # A value at a point, not a function: f'(3), "dy/dx at x = 2".
    at_point: bool = False
    integral: bool = False
    limit: bool = False
    behaviour: bool = False
    # The extreme values: "the local maximum and minimum values", "the absolute extrema".
    extreme_values: bool = False
    # Both the greatest and the least are asked.
    both_extremes: bool = False

    @property
    def calculus(self) -> bool:
        return bool(self.derivative_orders) or self.integral or self.limit

    @property
    def named(self) -> bool:
        """The question names any operation at all."""
        return self.calculus or self.behaviour


def _prime_orders(text: str) -> set[int]:
    """The order of each Lagrange prime that asks (``f''(x)``, ``y'``); one set to a value
    (``f'(x) = 3x^2``) is a given."""
    orders: set[int] = set()
    i = 0
    while i < len(text):
        run = lagrange_prime_run(text, i) if text[i] == "'" else None
        if run is None:
            i += 1
            continue
        after, order = run
        k = skip_optional_paren_var(text, after)
        if not text[k:].lstrip().startswith("="):
            orders.add(order)
        i = after
    return orders


def _derivative_orders(text: str) -> frozenset[int]:
    orders = _prime_orders(text)
    for match in _HIGHER_LEIBNIZ.finditer(text):
        orders.add(int(match.group(1)) if match.group(1) else _SUPERSCRIPT_ORDERS[match.group(2)])
    for match in _ORDINAL_DERIVATIVE.finditer(text):
        orders.add(_ORDINALS[match.group(1).lower()])
    # The plain verbs and notation, once the ordinals above have claimed theirs.
    plain = _HIGHER_LEIBNIZ.sub(" ", _ORDINAL_DERIVATIVE.sub(" ", text))
    words = {CALC_OP_SPELLINGS.get(w.lower(), w.lower()) for w in CALC_OP.findall(plain)}
    if words & _DERIVATIVE_WORDS or ddx_cue_at(plain) is not None or RATE_OF_CHANGE.search(plain):
        orders.add(1)
    return frozenset(orders)


def asked_operations(text: str) -> AskedOperations:
    """The operations ``text`` asks for (a model's reading of it, a tool call, a reader's
    equation are checked against these)."""
    text = text[:_MAX_TEXT].translate({0x2019: "'", 0x2032: "'", 0x2033: "''", 0x2034: "'''"})
    words = {CALC_OP_SPELLINGS.get(w.lower(), w.lower()) for w in CALC_OP.findall(text)}
    orders = _derivative_orders(text)
    return AskedOperations(
        derivative_orders=orders,
        at_point=bool(orders) and asks_at_a_point(text),
        integral=bool(words & _INTEGRAL_WORDS) or "∫" in text or bool(_ANTIDERIVATIVE.search(text)),
        limit=_LIMIT.search(text) is not None,
        behaviour=_BEHAVIOUR.search(text) is not None,
        extreme_values=_EXTREME_VALUES.search(text) is not None,
        both_extremes=bool(_MAXIMUM.search(text) and _MINIMUM.search(text)),
    )


def computes_the_ask(
    asked: AskedOperations, computation: Computation, *, order: int = 1, at_point: bool = False
) -> bool:
    """A ``computation`` computes what was ``asked``, not a step toward it.

    A derivative answers only a derivative asked, of its order, at a point when one is
    asked, and never a question about how the function behaves; an integral or a limit
    only that; a solve or a rewrite (simplify, factor, expand) none of these.
    """
    if computation == "derivative":
        return (
            asked.derivative_orders == {order}
            and not asked.behaviour
            and (at_point or not asked.at_point)
        )
    if computation == "integral":
        return asked.integral and not asked.behaviour
    if computation == "limit":
        return asked.limit and not asked.behaviour
    return not asked.named


# What each kind of computation is, as a SymPy tool call names it and as a reading does.
_CALL_COMPUTATIONS: dict[str, Computation] = {
    "solve": "solve",
    "system": "solve",
    "inequality": "solve",
    "diff": "derivative",
    "integrate": "integral",
    "limit": "limit",
    "simplify": "rewrite",
    "factor": "rewrite",
    "expand": "rewrite",
}
_READ_KINDS: dict[str, Computation] = {
    "equation": "solve",
    "system": "solve",
    "inequality": "solve",
    "limit": "limit",
}
_CALCULUS_OPERATIONS: dict[str, Computation] = {
    "differentiate": "derivative",
    "integrate": "integral",
    "simplify": "rewrite",
    "factor": "rewrite",
    "expand": "rewrite",
}


def reading_computes_the_ask(text: str, intent: MathIntent) -> bool:
    """A reading of ``text`` computes what it asks. A reading of another kind (a school
    operation, a geometry measure) is not judged here."""
    computation = _READ_KINDS.get(intent.kind)
    if intent.kind == "calculus" and not intent.school_op:
        computation = _CALCULUS_OPERATIONS.get(intent.operation or "")
    if computation is None:
        return True
    return computes_the_ask(
        asked_operations(text),
        computation,
        order=intent.derivative_order,
        at_point=intent.evaluation_point is not None,
    )


def call_computes_the_ask(text: str, args: dict[str, Any]) -> bool:
    """A SymPy tool call computes what ``text`` asks; a call of another kind (a graph, a
    shape, a series) is not judged here. The tool differentiates at no point."""
    computation = _CALL_COMPUTATIONS.get(str(args.get("action") or "solve").strip().lower())
    if computation is None:
        return True
    try:
        order = int(args.get("order") or 1)
    except (TypeError, ValueError):
        return False
    return computes_the_ask(asked_operations(text), computation, order=order)
