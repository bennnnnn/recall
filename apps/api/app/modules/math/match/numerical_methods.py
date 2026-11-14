"""A numerical method the question names, and the count or step it fixes.

"Use the trapezoidal rule with n = 4 to approximate the integral of x^2 from 0 to 2" asks
for T_4 = 2.75, not the integral, 8/3: the exact reading was certified, and a model's
correct 2.75 got "The verified answer is 8/3" under it (2026-11-13 audit, MATH-01). "Apply
1 Newton iteration to x^2 - 10 = 0 from x = 3" asks for x_1 = 19/6, not the root √10. A
method or a count named here and not carried by the reading makes the reading decline
(``request_consumption``); the methods the server works are read into the intent
(``tools/extractors/approximation.py``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.math.schemas.operations import NumericRule, WorkedNumericRule
from app.services.number_text import SIGNED_DECIMAL

INTEGRATION_RULES: frozenset[str] = frozenset({"trapezoid", "midpoint", "simpson", "left", "right"})

_SUM = r"(?:rule|method|approximation|sum|estimate)"
# First match wins: a rule the server does not work ("a Riemann sum" with no side, the
# improved Euler method) is ``unworked``, so no exact reading stands in for it.
_PATTERNS: tuple[tuple[NumericRule, str], ...] = (
    ("unworked", r"\b(?:improved|modified)\s+euler|\brunge[-\s]*kutta|\bheun|\brk4\b"),
    ("unworked", r"\b(?:lower|upper)\s+(?:riemann\s+)?sums?\b"),
    ("simpson", rf"\bsimpson(?:'s|\u2019s|s)?(?:\s+(?:1\s*/\s*3|one[-\s]third))?\s+{_SUM}"),
    ("trapezoid", rf"\btrapezoid(?:al)?\s+{_SUM}|\btrapezium\s+{_SUM}"),
    ("midpoint", rf"\bmid[-\s]?point\s+(?:riemann\s+)?{_SUM}"),
    ("left", rf"\bleft(?:[-\s]+(?:hand|end[-\s]?point))*\s+(?:riemann\s+)?{_SUM}"),
    ("right", rf"\bright(?:[-\s]+(?:hand|end[-\s]?point))*\s+(?:riemann\s+)?{_SUM}"),
    ("unworked", r"\briemann\s+sums?\b"),
    ("euler", r"\beuler(?:'s|\u2019s|s)?\s+method\b"),
    (
        "newton",
        r"\bnewton(?:'s|\u2019s|s)?(?:[-\s]+raphson)?\s+"
        r"(?:method|iterations?|steps?|iterates?|approximations?)\b|\bnewton[-\s]+raphson\b",
    ),
)
_RULES = tuple((rule, re.compile(pattern, re.IGNORECASE)) for rule, pattern in _PATTERNS)

_WORDS = {
    "a single": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "twenty": 20,
}  # fmt: skip
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}
_TIMES = {"once": 1, "twice": 2, "three times": 3}
_COUNT = rf"(?P<count>\d{{1,3}}|{'|'.join(_WORDS)})"
_PIECES = (
    r"(?:equal(?:ly\s+spaced)?\s+|equal[-\s]width\s+)?"
    r"(?P<piece>(?:sub)?intervals?|(?:sub)?divisions?|strips?|rectangles?|trapezoids?|"
    r"trapezi(?:a|ums?)|panels?|partitions?|slices?|segments?|ordinates?|points?)\b"
)
_INTERVAL_COUNT = re.compile(
    rf"\bn\s*=\s*(?P<n>\d{{1,3}})\b|{_COUNT}\s+{_PIECES}",
    re.IGNORECASE,
)
_STEP_COUNT = re.compile(
    rf"{_COUNT}\s+(?:newton(?:'s|\u2019s)?\s+|euler\s+)?(?:iterations?|steps?|iterates?)\b"
    rf"|\b(?P<ordinal>{'|'.join(_ORDINALS)})\s+(?:newton\s+)?(?:iteration|step)\b"
    rf"|\b(?P<times>{'|'.join(_TIMES)})\b",
    re.IGNORECASE,
)
# The iterate asked for by name: "find x_2", "x3, the third approximation". An iterate
# set to a value ("x_0 = 3") is the start, not an ask; a power (x^2) is no iterate.
_ITERATE = re.compile(
    rf"\b(?P<ordinal>{'|'.join(_ORDINALS)})\s+(?:approximation|estimate|iterate)\b"
    r"|(?<![\w^])[a-z]_?\{?(?P<index>\d)\}?(?![\w.]|\s*=)",
    re.IGNORECASE,
)


def _label(group: str) -> str:
    """``x_0 = `` before a starting value, its index (0 or 1) in ``group``."""
    return rf"(?:[a-z]_?\{{?(?P<{group}>[01])?\}}?\s*=\s*)"


# Where an iteration starts, and the index its value carries: "starting at 3", "from
# x = 3", "initial guess x_0 = 1", "x1 = 2".
_START = re.compile(
    rf"\b(?:(?:starting|start|beginning|begin)\s+(?:at|from|with)|"
    rf"(?:initial|starting|first)\s+(?:guess|approximation|value|estimate|point|iterate)"
    rf"(?:\s+(?:of|is|at))?\s*=?)\s*{_label('lead')}?(?P<a>{SIGNED_DECIMAL})"
    rf"|\b(?:from|with|at|near|using|taking)\s+{_label('after')}(?P<b>{SIGNED_DECIMAL})"
    rf"|\b[a-z]_?\{{?(?P<own>[01])\}}?\s*=\s*(?P<c>{SIGNED_DECIMAL})",
    re.IGNORECASE,
)
_STEP_SIZE = re.compile(
    rf"\bh\s*=\s*(?P<h>{SIGNED_DECIMAL})|\bstep(?:\s+(?:size|length|width))?\s*"
    rf"(?:of|=|is)?\s*(?P<step>{SIGNED_DECIMAL})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NamedMethod:
    rule: NumericRule
    # Subintervals for a rule of integration, steps for Newton or Euler; None when none is
    # named (Newton then runs to convergence).
    count: int | None = None
    # Newton: the index the starting value carries (x_0 or x_1), so x_3 is 3 or 2 steps.
    first_index: int = 0
    # Euler: the step h as written.
    step_size: str | None = None
    # Newton: the starting value as written, when the question gives one.
    start: str | None = None
    # A count was written that this reading could not take ("find x_1" from x_1).
    unread_count: bool = False
    # Newton: several iterates were asked for ("find x_1 and x_2"): the card holds each.
    every_iterate: bool = False


def named_numerical_method(text: str) -> NamedMethod | None:
    """The numerical method ``text`` names, with its count; None when it names none."""
    if len(text) > 2000:
        return None
    rule = next((rule for rule, pattern in _RULES if pattern.search(text)), None)
    if rule is None:
        return _method_by_parts(text)
    if rule in INTEGRATION_RULES:
        # "the trapezoidal rule and Simpson's rule", "left and right sums": every estimate
        # asked on the card, or none.
        rule = rule if len(_rules_asked(text)) <= 1 else "unworked"
        return NamedMethod(rule=rule, count=_interval_count(text))
    if rule == "euler":
        step = _STEP_SIZE.search(text)
        size = None if step is None else step.group("h") or step.group("step")
        return NamedMethod(rule=rule, count=_steps_named(text), step_size=size)
    if rule == "newton":
        return _newton(text)
    return NamedMethod(rule=rule)


# A sum asked for by its parts, with no rule's name: "Use 4 trapezoids to estimate …",
# "Using 4 rectangles and left endpoints, estimate …". Its count and an estimate (or an area
# under a curve, or an integral) make it a numerical method; the parts say which, and a sum
# whose side is not said is one no solver here works. Each was a checked exact 8/3 for the
# estimate 2.75, 1.75 or 3.75 (2026-11-14 review).
_TRAPEZOID_PIECES = re.compile(rf"{_COUNT}\s+(?:equal\s+)?trapez(?:oids|ia|iums)\b", re.I)
_LEFT_PARTS = re.compile(r"\bleft(?:[-\s]+hand)?[-\s]+(?:end[-\s]?points?|sides?|corners?)\b", re.I)
_RIGHT_PARTS = re.compile(
    r"\bright(?:[-\s]+hand)?[-\s]+(?:end[-\s]?points?|sides?|corners?)\b", re.I
)
_MIDPOINT_PARTS = re.compile(r"\bmid[-\s]?points?\b", re.I)
# What a sum of pieces estimates: an integral or an area under a curve. "Estimate the
# probability of 2 heads in 4 tosses … with n = 4" is no sum: it was 3/8, and the n read as a
# method's count took its card (2026-11-14 review).
_ESTIMATED_INTEGRAL = re.compile(
    r"\barea\s+(?:under|beneath|between)\b|\bunder\s+the\s+(?:curve|graph)\b|\bintegral\b"
    r"|\u222b",
    re.I,
)
# Each estimate a method question may name; two of them asked ("left endpoints and then right
# endpoints") carded one (2026-11-14 review).
_ESTIMATES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("trapezoid", re.compile(r"\btrapez(?:oid|ium|ia)", re.I)),
    ("simpson", re.compile(r"\bsimpson", re.I)),
    ("midpoint", re.compile(r"\bmid[-\s]?points?\b", re.I)),
    ("left", re.compile(r"\bleft\b", re.I)),
    ("right", re.compile(r"\bright\b", re.I)),
)


def _rules_asked(text: str) -> set[str]:
    return {rule for rule, pattern in _ESTIMATES if pattern.search(text)}


def _method_by_parts(text: str) -> NamedMethod | None:
    count = _interval_count(text)
    if count is None or _ESTIMATED_INTEGRAL.search(text) is None:
        return None
    rule: NumericRule = "unworked"
    if len(_rules_asked(text)) > 1:
        rule = "unworked"
    elif _TRAPEZOID_PIECES.search(text):
        rule = "trapezoid"
    elif _LEFT_PARTS.search(text):
        rule = "left"
    elif _RIGHT_PARTS.search(text):
        rule = "right"
    elif _MIDPOINT_PARTS.search(text):
        rule = "midpoint"
    return NamedMethod(rule=rule, count=count)


def worked_rule(named: NamedMethod) -> WorkedNumericRule | None:
    """The rule a solver here works, or None for one it does not."""
    return None if named.rule == "unworked" else named.rule


_METHOD_LEAD = r"(?:\b(?:use|using|apply|applying|with|by|via)\s+)?(?:\b(?:the|a|an)\s+)?"
_COUNT_LEAD = r"(?:\b(?:with|using|and|for|taking|where)\s+|,\s*)?"
_ESTIMATE = re.compile(
    r"\b(?:to\s+)?(?:approximate|estimate)(?:\s+the\s+value\s+of)?\b", re.IGNORECASE
)
_METHOD_CLAUSES = tuple(
    re.compile(rf"{_METHOD_LEAD}(?:{pattern.pattern})", re.IGNORECASE) for _rule, pattern in _RULES
)
_COUNT_CLAUSE = re.compile(rf"{_COUNT_LEAD}(?:{_INTERVAL_COUNT.pattern})", re.IGNORECASE)
# The parts that name a sum ("and left endpoints", "of equal width"), and a leading "use".
_PARTS_CLAUSES = re.compile(
    r"(?:\b(?:and|with|using|by|at)\s+)?(?:the\s+)?(?:(?:left|right)(?:[-\s]+hand)?[-\s]+"
    r"(?:end[-\s]?points?|sides?|corners?)|mid[-\s]?points?)\b|\bof\s+equal\s+width\b"
    r"|^\s*(?:use|using|apply)\b",
    re.IGNORECASE,
)


def without_named_method(text: str) -> str:
    """ "the integral of x^2 from 0 to 2": the question with its rule, its count and "to
    approximate" taken out, for the reader of what the rule is applied to."""
    for clause in _METHOD_CLAUSES:
        text = clause.sub(" ", text)
    text = _ESTIMATE.sub(" ", _COUNT_CLAUSE.sub(" ", text))
    text = _PARTS_CLAUSES.sub(" ", " ".join(text.split()).strip(" ,.;:"))
    return " ".join(text.split()).strip(" ,.;:")


def without_start(text: str) -> str:
    """The question with its starting value ("starting at x_0 = 1") taken out, so the
    equation is the one relation left in it."""
    return " ".join(_START.sub(" ", text).split())


def _number(word: str) -> int:
    return int(word) if word.isdigit() else _WORDS[word.lower()]


def _interval_count(text: str) -> int | None:
    found = _INTERVAL_COUNT.search(text)
    if found is None:
        return None
    if found.group("n"):
        return int(found.group("n"))
    count = _number(found.group("count"))
    # Five ordinates (or points) bound four strips.
    piece = found.group("piece").lower()
    return count - 1 if piece.startswith(("ordinate", "point")) else count


def _steps_named(text: str) -> int | None:
    found = _STEP_COUNT.search(text)
    if found is None:
        return None
    if found.group("count"):
        return _number(found.group("count"))
    if found.group("ordinal"):
        return _ORDINALS[found.group("ordinal").lower()]
    return _TIMES[found.group("times").lower()]


def _newton(text: str) -> NamedMethod:
    found = _START.search(text)
    value = None if found is None else found.group("a") or found.group("b") or found.group("c")
    index = None if found is None else found["lead"] or found["after"] or found["own"]
    first = int(index) if index else 0
    steps = _steps_named(text)
    if steps is not None:
        return NamedMethod(rule="newton", count=steps, first_index=first, start=value)
    # "find x_1 and x_2": the furthest iterate asked, every one before it worked too.
    targets = {
        _ORDINALS[asked.group("ordinal").lower()]
        if asked.group("ordinal")
        else int(asked.group("index"))
        for asked in _ITERATE.finditer(text)
    }
    if not targets:
        return NamedMethod(rule="newton", first_index=first, start=value)
    target = max(targets)
    if target <= first:
        return NamedMethod(rule="newton", first_index=first, start=value, unread_count=True)
    return NamedMethod(
        rule="newton",
        count=target - first,
        first_index=first,
        start=value,
        every_iterate=len(targets) > 1,
    )
