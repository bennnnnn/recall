"""The operations a question asks for: a derivative (its order, at a point or not, alone or
as one term of more), an integral, a limit, a rate, or how a function behaves (its extreme
values, where it rises and falls, its asymptotes and intercepts).

A computation answers the question only when it computes what the question asks
(``computes_the_ask``); any other is a step of the working. The equation solver read
"Find dy/dx for y = x ln x" as the equation y = x ln x and certified x = e^{W(y)} as the
derivative, and the model's own readings and SymPy calls held the user's formula but not
the question: f'(x) = 2x - 1 was the checked card for lim_{h->0} (f(3 + h) - f(3))/h
(asked: 5), the first derivative for d^2y/dx^2, and f'(x) for an absolute maximum and
minimum (2026-11-14, grade 12 book).

Only the sentences that ask are read ("The derivative of a function is 2x - 4. Solve 2x -
4 = 0." asks a solve), and only what they ask, not what they state: "f'(x) = 3x^2" and
"the rate of change of y with respect to x is 2x" are givens. The notation is the readers'
own (``calc_op``'s verbs, ``turn_reading.derivative_notation``); a word is read as an
operation only where it names one: "the limit of", not a speed limit; "the integral of",
not integral solutions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.math.match.asked_quantities import ASKS, asking_spans
from app.modules.math.match.calculus import lagrange_prime_run
from app.modules.math.match.scan import CALC_OP, CALC_OP_SPELLINGS
from app.modules.math.schemas import MathIntent
from app.modules.turn_reading.derivative_notation import LEIBNIZ, asks_at_a_point, leibniz_order
from app.services.glyphs import fold_operator_glyphs, fold_primes

_MAX_TEXT = 2000
# A sentence asks when it asks (``ASKS``) or names the operation to do.
_ASKS_AN_OPERATION = re.compile(
    ASKS.pattern + r"|\b(?:solve|differentiate|integrate|simplify|factori[sz]e|factor|expand"
    r"|sketch|graph|plot|identify)\b",
    re.IGNORECASE,
)
# What follows a quantity set to a value: "f'(x) = 3x^2", "... is 2x". "dy/dx = ?" asks.
_STATED = re.compile(r"\s*(?:=(?!\s*\?)|(?:is|are|was|equals)\b)", re.IGNORECASE)
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
# A derivative's noun phrase that a sentence then states: "the derivative of f is 2x".
_NAMED_THEN_STATED = re.compile(r"\s+of\s+[a-zA-Z](?:\s*\([^()]{0,20}\))?\s*(?:=|is\b)")
# How fast a quantity changes, asked by name: a velocity, a speed, an acceleration.
_RATE_QUANTITY = re.compile(r"\b(?:velocity|speed|acceleration)\b", re.IGNORECASE)
# A limit asked: lim, "the limit of", "the limit as x -> 2". A speed or time limit is none.
_LIMIT = re.compile(r"\blim(?![a-z])|\blimits?\s+(?:of|as|at|when|from)\b", re.IGNORECASE)
# An integral asked by its noun or sign; "integral solutions" are whole numbers.
_INTEGRAL_NOUN = re.compile(
    r"\b(?:definite|indefinite)\s+integral|\bintegral\s+(?:of|from)\b|∫|\banti-?deriv",
    re.IGNORECASE,
)
# How a function behaves, which a derivative is only a step to: its extreme values, where it
# rises, falls and bends, its asymptotes and intercepts.
_BEHAVIOUR = re.compile(
    r"\b(?:maxim(?:um|a|i[sz]e)|minim(?:um|a|i[sz]e)|extrem(?:um|a|e\s+values?)"
    r"|(?:local|absolute|relative|global)\s+(?:max|min)"
    r"|critical\s+(?:numbers?|points?|values?)|(?:stationary|turning)\s+points?"
    r"|inflections?|(?:points?\s+of\s+)?inflexion|concav(?:e|ity)|increasing|decreasing"
    r"|monoton(?:e|ic|icity)|asymptotes?|intercepts?)\b",
    re.IGNORECASE,
)
# The features of a function a question may list, each by kind: a sketch or a study of a
# function asks several ("the critical numbers, extreme values, intervals ... and sketch").
_FEATURES = re.compile(
    r"(?P<extreme>\b(?:maxim(?:um|a)|minim(?:um|a)|extrem(?:um|a|e)|critical|stationary"
    r"|turning\s+points?)\b)"
    r"|(?P<monotonic>\b(?:increas\w*|decreas\w*|monoton\w*)\b)"
    r"|(?P<concavity>\b(?:concav\w*|inflect\w*|inflexion|bends?)\b)"
    r"|(?P<asymptote>\basymptot\w*)|(?P<intercept>\bintercepts?\b)|(?P<hole>\bholes?\b)"
    r"|(?P<continuity>\b(?:continuous|continuity|discontinu\w*)\b)"
    r"|(?P<drawn>\b(?:sketch|graph|plot)\w*)",
    re.IGNORECASE,
)
_REWRITE_WORDS = frozenset({"simplify", "factor", "expand"})
# Of those, the extreme values themselves: where the function turns is a step to them.
_EXTREME_VALUES = re.compile(
    r"\b(?:maxim(?:um|a)|minim(?:um|a)|extrem(?:um|a|e\s+values?)"
    r"|(?:local|absolute|relative|global)\s+(?:max|min))\b",
    re.IGNORECASE,
)
# The greatest and the least, each: "the local maximum and minimum values".
_MAXIMUM = re.compile(r"\b(?:maxim(?:um|a)|greatest|largest|highest)\b", re.IGNORECASE)
_MINIMUM = re.compile(r"\b(?:minim(?:um|a)|least|smallest|lowest)\b", re.IGNORECASE)
# Where or when something happens, not its value: "the x-coordinate of", "when is it".
_LOCATION = re.compile(
    r"\b(?:when|where)\b|\b(?:at|for)\s+what\b|\b[a-z]-coordinates?\b", re.IGNORECASE
)
# What joins a derivative to more: an operator or a number beside it, or "and".
_OPERATOR = "+-*/^"
_LONE_LETTER = re.compile(r"(?<![A-Za-z])[B-HJ-Zb-z]$")
_AND_BEFORE = re.compile(r"(?:\band|&)$", re.IGNORECASE)
_AND_AFTER = re.compile(r"(?:and\b|&)", re.IGNORECASE)
_DERIVATIVE_WORDS = frozenset({"differentiate", "derivative"})
Computation = Literal["solve", "derivative", "integral", "limit", "rewrite"]


@dataclass(frozen=True)
class AskedOperations:
    """What a question asks to be computed."""

    derivative_orders: frozenset[int] = frozenset()
    # A value at a point, not a function: f'(3), "dy/dx at x = 2".
    at_point: bool = False
    # The derivative asked is one term of more ("f'(3) - f(3)", "2 dy/dx") or one of two
    # asks ("dy/dx and the value of y").
    combined: bool = False
    integral: bool = False
    limit: bool = False
    # A rate asked by name ("the velocity at t = 2"): a derivative of a given formula.
    rate: bool = False
    behaviour: bool = False
    # The extreme values: "the local maximum and minimum values", "the absolute extrema".
    extreme_values: bool = False
    # Both the greatest and the least are asked.
    both_extremes: bool = False
    # Where or when, not how much: "the x-coordinate of the minimum", "when is it highest".
    location: bool = False
    # How many kinds of a function's features it asks: two or more is a study of the
    # function, which no one value answers.
    features: int = 0
    # A rewrite asked by name: simplify, factor, expand.
    rewrite: bool = False

    @property
    def calculus(self) -> bool:
        return bool(self.derivative_orders) or self.integral or self.limit or self.rate

    @property
    def named(self) -> bool:
        """The question names any operation at all."""
        return self.calculus or self.behaviour


def _asking_sentences(text: str) -> list[str]:
    """The sentences of ``text`` that ask, in the readers' spelling of primes and operators."""
    text = fold_operator_glyphs(fold_primes(text[:_MAX_TEXT]))
    return [text[start:end] for start, end in asking_spans(text, _ASKS_AN_OPERATION)]


def _stated(text: str, end: int) -> bool:
    return _STATED.match(text, end) is not None


def _prime_derivatives(text: str) -> list[tuple[int, int, int]]:
    """``(start, end, order)`` of each Lagrange prime that asks (``f''(x)``, ``y'``, ``f'(3)``
    with its bracket); one set to a value (``f'(x) = 3x^2``) is a given."""
    found: list[tuple[int, int, int]] = []
    i = 0
    while i < len(text):
        run = lagrange_prime_run(text, i) if text[i] == "'" else None
        if run is None:
            i += 1
            continue
        after, order = run
        start = i
        while start > 0 and text[start - 1].isalpha():
            start -= 1
        end = after
        if text[after : after + 1] == "(" and ")" in text[after : after + 24]:
            end = text.index(")", after) + 1
        if not _stated(text, end):
            found.append((start, end, order))
        i = after
    return found


def _joined(text: str, start: int, end: int, *, operand_after: bool) -> bool:
    """The derivative written at ``text[start:end]`` is one term of more, or one of two asks.

    A bracket round it alone is its own ("x(dy/dx)" looks outside it). d/dx is followed by
    what it differentiates, so only what stands before it counts.
    """
    while 0 < start and end < len(text) and text[start - 1] == "(" and text[end] == ")":
        start, end = start - 1, end + 1
    before, after = text[:start].rstrip(), text[end:].lstrip()
    if before[-1:] in tuple(_OPERATOR + ")") or before[-1:].isdigit():
        return True
    if _LONE_LETTER.search(before) or _AND_BEFORE.search(before):
        return True
    if _AND_AFTER.match(after):
        return True
    if not operand_after:
        return False
    glued = text[end : end + 1]
    return after[:1] in tuple(_OPERATOR) or glued.isalnum() or glued == "("


def _derivatives(text: str) -> tuple[frozenset[int], bool]:
    """The orders of the derivatives ``text`` asks, and whether one is joined to more."""
    orders: set[int] = set()
    combined = False
    for start, end, order in _prime_derivatives(text):
        orders.add(order)
        combined = combined or _joined(text, start, end, operand_after=True)
    for match in LEIBNIZ.finditer(text):
        if _stated(text, match.end()):
            continue
        orders.add(leibniz_order(match))
        combined = combined or _joined(
            text, match.start(), match.end(), operand_after=match["of"] is not None
        )
    for match in _ORDINAL_DERIVATIVE.finditer(text):
        orders.add(_ORDINALS[match.group(1).lower()])
    # The plain verbs and the rate, once the ordinals above have claimed theirs.
    plain = _ORDINAL_DERIVATIVE.sub(" ", text)
    for match in CALC_OP.finditer(plain):
        word = CALC_OP_SPELLINGS.get(match.group(1).lower(), match.group(1).lower())
        if word in _DERIVATIVE_WORDS and not _NAMED_THEN_STATED.match(plain, match.end()):
            orders.add(1)
    if any(not _stated(plain, m.end()) for m in RATE_OF_CHANGE.finditer(plain)):
        orders.add(1)
    return frozenset(orders), combined


def asks_rate_of_change(text: str) -> bool:
    """``text`` asks the rate of change of one letter with respect to another."""
    return any(
        not _stated(sentence, m.end())
        for sentence in _asking_sentences(text)
        for m in RATE_OF_CHANGE.finditer(sentence)
    )


def asked_operations(text: str) -> AskedOperations:
    """The operations ``text`` asks for (a model's reading of it, a tool call, a reader's
    equation are checked against these)."""
    sentences = _asking_sentences(text)
    asked = "\n".join(sentences)
    read = [_derivatives(sentence) for sentence in sentences]
    orders = frozenset().union(*(found for found, _joined_up in read))
    combined = any(joined_up for _found, joined_up in read)
    words = {CALC_OP_SPELLINGS.get(w.lower(), w.lower()) for w in CALC_OP.findall(asked)}
    rate = any(not _stated(asked, m.end()) for m in _RATE_QUANTITY.finditer(asked))
    return AskedOperations(
        derivative_orders=orders,
        at_point=bool(orders or rate) and asks_at_a_point(asked),
        combined=combined,
        integral="integrate" in words or _INTEGRAL_NOUN.search(asked) is not None,
        limit=_LIMIT.search(asked) is not None,
        rate=rate,
        behaviour=_BEHAVIOUR.search(asked) is not None,
        extreme_values=_EXTREME_VALUES.search(asked) is not None,
        both_extremes=bool(_MAXIMUM.search(asked) and _MINIMUM.search(asked)),
        location=_LOCATION.search(asked) is not None,
        features=len({m.lastgroup for m in _FEATURES.finditer(asked)}),
        rewrite=bool(words & _REWRITE_WORDS),
    )


def derivative_answers(asked: AskedOperations, order: int, *, at_point: bool) -> bool:
    """A derivative of ``order`` is all that was asked: no other order, no other term, and
    a value when a point is asked."""
    return (
        asked.derivative_orders == {order}
        and not asked.combined
        and (at_point or not asked.at_point)
    )


def computes_the_ask(
    asked: AskedOperations, computation: Computation, *, order: int = 1, at_point: bool = False
) -> bool:
    """A ``computation`` computes what was ``asked``, not a step toward it.

    A derivative answers only a derivative asked (``derivative_answers``), never a question
    about how the function behaves; an integral or a limit only that; a solve no
    derivative, integral, limit or rate asked, nor a study of a function's several
    features; a rewrite (simplify, factor, expand) the same, and only when it is asked.
    """
    if computation == "derivative":
        return derivative_answers(asked, order, at_point=at_point) and not asked.behaviour
    if computation == "integral":
        return asked.integral and not asked.behaviour
    if computation == "limit":
        return asked.limit and not asked.behaviour
    if asked.calculus or asked.features > 1:
        return False
    # The function rewritten is no answer unless a rewrite is asked: "the largest intervals
    # on which 4|x^2 - 1|/(x - 1) is continuous" had the function itself as its card.
    return computation == "solve" or asked.rewrite


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
# A school reading whose answer one SymPy operation computes: a curve's slope is its
# derivative.
_SCHOOL_COMPUTATIONS: dict[str, Computation] = {"equation_slope": "derivative"}
# A value the user's numbers make (1.200 + 800, (3 + 2i)(1 - i)): any rewrite computes it.
_VALUE_KINDS = frozenset({"arithmetic", "complex"})


def _read_computation(intent: MathIntent) -> Computation | None:
    if intent.school_op in _SCHOOL_COMPUTATIONS:
        return _SCHOOL_COMPUTATIONS[intent.school_op]
    if intent.kind in _VALUE_KINDS:
        return "rewrite"
    if intent.school_op:
        return None
    if intent.kind == "calculus":
        return _CALCULUS_OPERATIONS.get(intent.operation or "")
    return _READ_KINDS.get(intent.kind)


def _call_computation(args: dict[str, Any]) -> tuple[Computation, int] | None:
    """The kind and order a SymPy tool call computes; None for a kind not judged here (a
    graph, a shape, a series). An order that is no number is read as none asked (0)."""
    computation = _CALL_COMPUTATIONS.get(str(args.get("action") or "solve").strip().lower())
    if computation is None:
        return None
    try:
        return computation, int(args.get("order") or 1)
    except (TypeError, ValueError):
        return computation, 0


def reading_computes_the_ask(text: str, intent: MathIntent) -> bool:
    """A model's reading of ``text`` computes what it asks. A reading of another kind (a
    school operation, a geometry measure) is not judged here."""
    computation = None if intent.school_op else _read_computation(intent)
    if computation is None:
        return True
    return computes_the_ask(
        asked_operations(text),
        computation,
        order=intent.derivative_order,
        at_point=intent.evaluation_point is not None,
    )


def call_computes_the_ask(text: str, args: dict[str, Any]) -> bool:
    """A SymPy tool call computes what ``text`` asks. The tool differentiates at no point."""
    call = _call_computation(args)
    if call is None:
        return True
    return computes_the_ask(asked_operations(text), call[0], order=call[1])


def call_answers_reading(args: dict[str, Any], intent: MathIntent) -> bool:
    """A SymPy tool call computes what the server's own reading of the question computes:
    its kind, a derivative's order, and no point the tool cannot evaluate at. A reading no
    one operation computes (a curve's extreme values, a sketch) leaves every call a step."""
    call = _call_computation(args)
    if call is None:
        return True
    read = _read_computation(intent)
    if read != call[0]:
        return False
    if read != "derivative":
        return True
    order = 1 if intent.school_op else intent.derivative_order
    return call[1] == order and intent.evaluation_point is None


_SOLUTION_SETS = frozenset({"equation", "system", "inequality"})
_DIFFERENTIATED_READINGS = frozenset({None, "implicit"})


def unasked_reading(text: str, intent: MathIntent) -> list[str]:
    """Why a reader's reading of ``text`` computes something its asking sentences do not
    ask; none when it computes what they ask.

    - "Find dy/dx for y = x ln x" read as the equation y = x ln x certified x = e^{W(y)};
      no solve answers a derivative, integral, limit or rate asked ("the velocity at t = 2"
      of s = 3t^2 + 4t was "s = 20").
    - A derivative answers its own order, at its point, alone: "f'(x) and f''(x)", "f'(3) -
      f(3)", "2 dy/dx". The orders read only where the notation writes some: "the
      gradient at x = 3" is the reader's own.
    - The relative extrema of x + 4/x were a checked "-2, 2", where it turns; the local
      maximum and minimum values of x^3 - 6x^2 + 9x + 1 a checked 5, one of two; the
      x-coordinate of a minimum its value (2026-11-14).
    """
    asked = asked_operations(text)
    why: list[str] = []
    if intent.kind in _SOLUTION_SETS and asked.calculus:
        why.append("a derivative, integral, limit or rate asked, not solutions")
    differentiated = intent.kind == "calculus" and intent.operation == "differentiate"
    if differentiated and intent.school_op in _DIFFERENTIATED_READINGS and asked.derivative_orders:
        at_point = intent.evaluation_point is not None
        if not derivative_answers(asked, intent.derivative_order, at_point=at_point):
            why.append("another derivative asked, or this one as a term of more")
    if intent.operation == "critical_points" and not intent.school_op and asked.extreme_values:
        why.append("extreme values asked, not the critical points")
    if intent.school_op == "extreme_value" and (asked.both_extremes or asked.location):
        why.append("both extremes, or where one is, asked; one value read")
    return why
