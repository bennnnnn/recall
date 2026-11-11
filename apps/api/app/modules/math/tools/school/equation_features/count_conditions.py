"""What a solution count is taken over, read off the request before the equation is.

"how many solutions are there in [0, 5] to x^2 = 4" asks for one solution, not two. The
interval, the inequality and the sign word ("positive") each restrict the count, and a
count that ignored one was a wrong verified answer (review of 2026-11-10). Each form is
cut out of the request whole, up to where it ends (the end of the line, "and", a comma or
the bracket that closes it); anything that still reads as a condition afterwards ("in
integers", "mod 9", a bracket or an inequality left over) means the request is not read,
and the model answers.

``count_region`` then reads each part with the parser the equation is read with, and
takes only what it can solve exactly and at once (an allowlist, review of 2026-11-10):
relations ``<``, ``>``, ``<=``, ``>=`` and ``!=`` between sides that are polynomials in
the unknown with rational coefficients, degree 4 at most and short; bounds that are
rational. ``2x > 3``, ``-x > 0``, ``x > 2^2`` and ``x != 2`` read alike. Anything else
declines: a function (``sin(x) > 0`` is no single period), a higher degree (``x^50 > 3``
held a worker for 20 s), an irrational bound, another letter, a set that is not one
interval less some points, bounds given backwards, or text no part consumes. A bound
read only up to its first number counted the solutions of a different question
("for x > -2 + 3" as x > -2).

"counting multiplicity" is read here too: it changes what is counted, not the equation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

# The keyboard's relations, written the way the parser reads them.
_RELATIONS = (
    (re.compile(r"\\leq?(?![A-Za-z])|≤|⩽"), "<="),
    (re.compile(r"\\geq?(?![A-Za-z])|≥|⩾"), ">="),
    (re.compile(r"\\lt(?![A-Za-z])"), "<"),
    (re.compile(r"\\gt(?![A-Za-z])"), ">"),
    (re.compile(r"\\neq?(?![A-Za-z])|≠"), "!="),
)
# Where a condition ends: "and", a comma, a semicolon, a question mark, a full stop.
_END = r"(?=\s+and\s+|\s*[,;?]|\.(?:\s|$)|\s*$)"
# A condition's text: anything up to its end, with "=" only inside "<=", ">=" or "!=".
_TEXT = r"(?:[^,;?=]|(?<=[<>!])=)+?"
_LEAD = r"\b(?:for|if|where|when|with|such\s+that|given(?:\s+that)?|in|on|and)\s+"
_LIE = r"(?:\b(?:that\s+)?(?:lie|lies|lying|are)\s+)?"
_IN = (
    r"(?:\b(?:in|on|over|within|inside)\s+(?:the\s+)?(?:interval\s+|range\s+|domain\s+)?"
    r"|(?<![A-Za-z])(?P<named>[a-zA-Z])\s*(?:\\in(?![A-Za-z])|∈|\bin\b)\s*)"
)
_BRACKETS = re.compile(
    rf"(?:{_LEAD})?{_LIE}{_IN}(?P<open>[\[(])(?P<lo>[^\[\](),]+),(?P<hi>[^\[\](),]+)"
    r"(?P<close>[\])])",
    re.I,
)
# Both ends may or may not count: "between 0 and 5".
_BETWEEN = re.compile(
    rf"(?:{_LEAD})?{_LIE}\bbetween\s+(?P<lo>{_TEXT})\s+and\s+(?P<hi>{_TEXT}){_END}", re.I
)
_INEQUALITY = re.compile(rf"{_LEAD}(?P<text>{_TEXT}){_END}", re.I)
_SIGN = re.compile(
    r"(?:\b(?:for|if|where|when|with)\s+(?:(?P<var>[a-zA-Z])\s+(?:is\s+)?)?)?"
    r"\b(?P<sign>non-?negative|non-?positive|positive|negative)\b"
    r"(?:\s+(?:values?\s+of\s+)?(?P<after>[a-zA-Z])\b(?!\s*[=^(]))?",
    re.I,
)
_MULTIPLICITY = re.compile(
    r"[,(]?\s*\b(?:when\s+)?(?:counting|counted(?:\s+with)?|with|including)\s+"
    r"(?:their\s+|the\s+|its\s+)?multiplicit(?:y|ies)\b\s*\)?",
    re.I,
)
# What still reads as a condition once the read ones are cut out.
_UNREAD = re.compile(
    r"[\[\]<>∈≡≠!]|\\in(?![A-Za-z])"
    r"|\b(?:between|positive|negative|integers?|integral|natural|whole|rational|irrational|"
    r"interval|domain|range|mod|modulo|multiplicit(?:y|ies)|greater|less|than|least|most|"
    r"lie|lies|lying|where|if|when|with|such|given|except|excluding|only|degrees?|radians?)\b",
    re.I,
)
_RELATION = re.compile(r"<=|>=|!=|<|>")
# The allowlist's limits: the degree and the length of one side.
_MAX_DEGREE = 4
_MAX_SIDE = 40


@dataclass(frozen=True)
class CountConditions:
    """The conditions as written: inequalities (``-x > 0``), intervals (open, low, high,
    close), "between" (low, high), sign words, the letter they name, and whether
    multiplicity is counted."""

    inequalities: tuple[str, ...] = ()
    intervals: tuple[tuple[str, str, str, str], ...] = ()
    between: tuple[tuple[str, str], ...] = ()
    named: frozenset[str] = frozenset()
    multiplicity: bool = False


@dataclass(frozen=True)
class CountRegion:
    """One interval less some points; ``None`` bounds are unbounded, ``None`` closedness
    either reading."""

    lower: str | None
    upper: str | None
    lower_closed: bool | None
    upper_closed: bool | None
    excluded: tuple[str, ...] = ()


def read_count_conditions(body: str) -> tuple[str, CountConditions] | None:
    """The request without its conditions, and the conditions; None when part of a
    condition is left that no form here reads."""
    multiplicity = _MULTIPLICITY.search(body) is not None
    rest = _MULTIPLICITY.sub(" ", body).replace("$", " ")
    for pattern, relation in _RELATIONS:
        rest = pattern.sub(f" {relation} ", rest)
    named: set[str] = set()
    intervals = []
    for found in _BRACKETS.finditer(rest):
        intervals.append((found["open"], found["lo"], found["hi"], found["close"]))
        named |= {found["named"]} if found["named"] else set()
    rest = _BRACKETS.sub(" ", rest)
    between = [(found["lo"], found["hi"]) for found in _BETWEEN.finditer(rest)]
    rest = _BETWEEN.sub(" ", rest)
    inequalities = []
    for found in _INEQUALITY.finditer(rest):
        if _RELATION.search(found["text"]):
            inequalities.append(found["text"])
            rest = rest.replace(found.group(0), " ", 1)
    for found in _SIGN.finditer(rest):
        sign = found["sign"].lower().replace("-", "")
        letter = found["var"] or found["after"]
        named |= {letter} if letter else set()
        inequalities.append(
            f"{letter or '_'} {'>' if sign in {'positive', 'nonnegative'} else '<'}"
            f"{'=' if sign.startswith('non') else ''} 0"
        )
    rest = _SIGN.sub(" ", rest)
    if _UNREAD.search(rest):
        return None
    conditions = CountConditions(
        inequalities=tuple(inequalities),
        intervals=tuple(intervals),
        between=tuple(between),
        named=frozenset(letter.lower() for letter in named),
        multiplicity=multiplicity,
    )
    return " ".join(rest.split()), conditions


def count_region(conditions: CountConditions, name: str) -> CountRegion | None:
    """The one interval, less some points, the conditions leave for the unknown ``name``;
    an unbounded one when there are none; None when a part is outside the allowlist or the
    set is no interval."""
    from sympy import Interval, S, Symbol, oo

    if conditions.named - {name.lower()}:
        # "for t > 0" about an equation in x is not a condition on its unknown.
        return None
    x = Symbol(name)
    region: Any = S.Reals
    points: set[Any] = set()
    either = False
    for opening, low, high, closing in conditions.intervals:
        lo, hi = _constant(low), _constant(high)
        if lo is None or hi is None or not lo < hi:
            return None
        region &= Interval(lo, hi, opening == "(", closing == ")")
    for low, high in conditions.between:
        lo, hi = _constant(low), _constant(high)
        if lo is None or hi is None or not lo < hi:
            return None
        region &= Interval(lo, hi)
        either = True
    for text in conditions.inequalities:
        solved = _solved(text.replace("_", name), x)
        if solved is None:
            return None
        allowed, removed = solved
        region &= allowed
        points |= removed
    if (not isinstance(region, Interval) and region != S.Reals) or region.measure == 0:
        # A union ("x^2 > 4"), a point or nothing: not one interval to count over.
        return None
    lower = None if region.inf == -oo else str(region.inf)
    upper = None if region.sup == oo else str(region.sup)
    return CountRegion(
        lower,
        upper,
        None if either else lower is not None and region.inf in region,
        None if either else upper is not None and region.sup in region,
        tuple(str(point) for point in sorted(points)),
    )


def _constant(text: str) -> Any | None:
    """A bound read whole: a rational number, or infinity."""
    from sympy import oo

    from app.modules.math.tools.school.equation_features.parsing import parse_side

    plain = text.replace("∞", "oo")
    plain = re.sub(r"\\infty|infinity", "oo", plain).strip()
    if len(plain) > _MAX_SIDE:
        return None
    try:
        value = parse_side(plain, [])
    except (ValueError, TypeError):  # SolveServiceError is a ValueError: no bound read.
        return None
    if value in (oo, -oo) or value.is_Rational:
        return value
    return None


def _polynomial(text: str, x: Any) -> Any | None:
    """One side, when it is a short polynomial in ``x`` with rational coefficients."""
    from sympy import Poly

    from app.modules.math.tools.school.equation_features.parsing import parse_side

    if len(text) > _MAX_SIDE:
        return None
    try:
        value = parse_side(text, [str(x)])
    except (ValueError, TypeError):  # SolveServiceError too: the side does not read.
        return None
    if value.free_symbols - {x} or not value.is_polynomial(x):
        return None
    poly = Poly(value, x)
    if poly.degree() > _MAX_DEGREE or not all(c.is_Rational for c in poly.all_coeffs()):
        return None
    return poly


def _solved(text: str, x: Any) -> tuple[Any, set[Any]] | None:
    """``1 < x + 1 <= 5`` as the set of x it allows, and the points ``x != 2`` removes;
    None unless every part is on the allowlist and every point it turns on is rational."""
    from sympy import S

    parts = _RELATION.split(text)
    relations = _RELATION.findall(text)
    if not 1 <= len(relations) <= 2 or ("!=" in relations and len(relations) != 1):
        return None
    read = [_polynomial(part.strip(), x) for part in parts]
    sides = [side for side in read if side is not None]
    if len(sides) != len(read) or all(side.degree() < 1 for side in sides):
        return None
    allowed: Any = S.Reals
    removed: set[Any] = set()
    for left, relation, right in zip(sides, relations, sides[1:], strict=False):
        difference = left - right
        turns = _rational_roots(difference)
        if turns is None:
            return None
        if relation == "!=":
            removed |= set(turns)
        else:
            allowed &= _sign_chart(difference, turns, relation)
    return allowed, removed


def _rational_roots(poly: Any) -> list[Any] | None:
    """The real roots of a polynomial of degree 4 at most, when all are rational."""
    if poly.degree() < 1:
        return []
    found = sorted(set(poly.real_roots()))
    return found if all(root.is_Rational for root in found) else None


def _sign_chart(poly: Any, turns: list[Any], relation: str) -> Any:
    """Where ``poly`` (relation) 0 holds, from its sign between and at its roots."""
    from sympy import FiniteSet, Interval, Rational, S, oo

    def holds(value: Any) -> bool:
        sign = poly.eval(value)
        return bool({"<": sign < 0, "<=": sign <= 0, ">": sign > 0, ">=": sign >= 0}[relation])

    edges = [-oo, *turns, oo]
    allowed: Any = S.EmptySet
    for low, high in pairwise(edges):
        if low == -oo and high == oo:
            middle = Rational(0)
        elif low == -oo:
            middle = high - 1
        elif high == oo:
            middle = low + 1
        else:
            middle = (low + high) / 2
        if holds(middle):
            allowed |= Interval.open(low, high)
    for turn in turns:
        if holds(turn):
            allowed |= FiniteSet(turn)
    return allowed
