"""What a solution count is taken over, read off the request before the equation is.

"how many solutions are there in [0, 5] to x^2 = 4" asks for one solution, not two. The
interval, the inequality and the sign word ("positive") each restrict the count, and a
count that ignored one was a wrong verified answer (review of 2026-11-10). Each form read
here is cut out of the request and kept as bounds; anything that still reads as a
condition afterwards ("in integers", "mod 9", a bracket or an inequality left over) means
the request is not read, and the model answers.

"counting multiplicity" is read here too: it changes what is counted, not the equation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A bound: a number, a fraction, a multiple of pi, or infinity.
_NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*/\s*\d+)?"
_BOUND = (
    rf"(?:[+-]?(?:\d+(?:\.\d+)?)?\s*\*?\s*(?:\\pi|pi|π)(?:\s*/\s*\d+)?"
    rf"|[+-]?\s*(?:\\infty|oo|∞|infinity)|{_NUMBER})"
)
_LESS = r"(?:<=|<|≤|\\leq?(?![A-Za-z])|\\lt(?![A-Za-z]))"
_MORE = r"(?:>=|>|≥|\\geq?(?![A-Za-z])|\\gt(?![A-Za-z]))"
# The words that open a condition: "for x > 0", "where 1 <= x <= 3", "with x in [1, 3]".
_LEAD = r"(?:\b(?:for|if|where|when|with|such\s+that|given(?:\s+that)?)\s+)?"
_LIE = r"(?:\b(?:that\s+)?(?:lie|lies|lying|are)\s+)?"
_IN = (
    r"(?:\b(?:in|on|over|within|inside)\s+(?:the\s+)?(?:interval\s+|range\s+|domain\s+)?"
    r"|(?<![A-Za-z])(?P<named>[a-zA-Z])\s*(?:\\in(?![A-Za-z])|∈|\bin\b)\s*)"
)
_VAR = r"(?<![\w^)\\])(?P<var>[a-zA-Z])(?![\w^(])"

_BRACKETS = re.compile(
    rf"{_LEAD}{_LIE}{_IN}(?P<open>[\[(])\s*(?P<lo>{_BOUND})\s*,\s*(?P<hi>{_BOUND})\s*(?P<close>[\])])",
    re.I,
)
_CHAIN_UP = re.compile(
    rf"{_LEAD}(?:\b(?:in|on)\s+)?(?P<lo>{_BOUND})\s*(?P<lo_op>{_LESS})\s*{_VAR}\s*"
    rf"(?P<hi_op>{_LESS})\s*(?P<hi>{_BOUND})",
    re.I,
)
_CHAIN_DOWN = re.compile(
    rf"{_LEAD}(?:\b(?:in|on)\s+)?(?P<hi>{_BOUND})\s*(?P<hi_op>{_MORE})\s*{_VAR}\s*"
    rf"(?P<lo_op>{_MORE})\s*(?P<lo>{_BOUND})",
    re.I,
)
_ONE_SIDE = re.compile(rf"{_LEAD}{_VAR}\s*(?P<op>{_LESS}|{_MORE})\s*(?P<bound>{_BOUND})", re.I)
# Both ends may or may not count: "between 0 and 5".
_BETWEEN = re.compile(rf"{_LEAD}{_LIE}\bbetween\s+(?P<lo>{_BOUND})\s+and\s+(?P<hi>{_BOUND})", re.I)
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
    rf"[\[\]<>≤≥∈≡]|{_LESS}|{_MORE}|\\in(?![A-Za-z])"
    r"|\b(?:between|positive|negative|integers?|integral|natural|whole|rational|irrational|"
    r"interval|domain|range|mod|modulo|multiplicit(?:y|ies)|greater|less|than|least|most|"
    r"lie|lies|lying|where|if|when|with|such|given|except|excluding|only|degrees?|radians?)\b",
    re.I,
)


@dataclass(frozen=True)
class CountConditions:
    """The bounds the count is taken over (None: unbounded on that side). ``closed`` is
    None for "between", where either reading may be meant."""

    lower: str | None = None
    upper: str | None = None
    lower_closed: bool | None = False
    upper_closed: bool | None = False
    variable: str | None = None
    multiplicity: bool = False

    @property
    def bounded(self) -> bool:
        return self.lower is not None or self.upper is not None


@dataclass
class _Reading:
    lower: str | None = None
    upper: str | None = None
    lower_closed: bool | None = False
    upper_closed: bool | None = False
    variables: set[str] | None = None
    conflict: bool = False

    def bound(self, side: str, value: str, closed: bool | None) -> None:
        if getattr(self, side) is not None:
            # Two bounds on one side: not one of the shapes read here.
            self.conflict = True
        setattr(self, side, value)
        setattr(self, f"{side}_closed", closed)

    def name(self, variable: str | None) -> None:
        if variable:
            self.variables = (self.variables or set()) | {variable.lower()}


def _bound(text: str) -> str:
    plain = re.sub(r"\s+", "", text).replace("\\pi", "pi").replace("π", "pi")
    plain = re.sub(r"(?<=\d)(?=pi)", "*", plain)
    for infinity in ("\\infty", "infinity", "∞"):
        plain = plain.replace(infinity, "oo")
    return plain


def _closed(op: str) -> bool:
    return "=" in op or "≤" in op or "≥" in op or op.lower().rstrip("q") in {"\\le", "\\ge"}


def _read_one(found: re.Match[str], reading: _Reading, pattern: re.Pattern[str]) -> None:
    groups = found.groupdict()
    if pattern is _BRACKETS:
        reading.name(groups.get("named"))
        reading.bound("lower", _bound(groups["lo"]), groups["open"] == "[")
        reading.bound("upper", _bound(groups["hi"]), groups["close"] == "]")
    elif pattern in (_CHAIN_UP, _CHAIN_DOWN):
        reading.name(groups["var"])
        reading.bound("lower", _bound(groups["lo"]), _closed(groups["lo_op"]))
        reading.bound("upper", _bound(groups["hi"]), _closed(groups["hi_op"]))
    elif pattern is _ONE_SIDE:
        reading.name(groups["var"])
        side = "lower" if re.match(_MORE, groups["op"]) else "upper"
        reading.bound(side, _bound(groups["bound"]), _closed(groups["op"]))
    elif pattern is _BETWEEN:
        reading.bound("lower", _bound(groups["lo"]), None)
        reading.bound("upper", _bound(groups["hi"]), None)
    else:
        reading.name(groups.get("var") or groups.get("after"))
        sign = groups["sign"].lower().replace("-", "")
        side = "lower" if sign in {"positive", "nonnegative"} else "upper"
        reading.bound(side, "0", sign.startswith("non"))


def read_count_conditions(body: str) -> tuple[str, CountConditions] | None:
    """The request without its conditions, and the conditions; None when part of a
    condition is left that no form here reads."""
    multiplicity = _MULTIPLICITY.search(body) is not None
    rest = _MULTIPLICITY.sub(" ", body)
    reading = _Reading()
    for pattern in (_BRACKETS, _CHAIN_UP, _CHAIN_DOWN, _BETWEEN, _ONE_SIDE, _SIGN):
        for found in list(pattern.finditer(rest)):
            _read_one(found, reading, pattern)
        rest = pattern.sub(" ", rest)
    if reading.conflict or _UNREAD.search(rest) or len(reading.variables or ()) > 1:
        return None
    conditions = CountConditions(
        lower=reading.lower,
        upper=reading.upper,
        lower_closed=reading.lower_closed,
        upper_closed=reading.upper_closed,
        variable=next(iter(reading.variables)) if reading.variables else None,
        multiplicity=multiplicity,
    )
    return " ".join(rest.split()), conditions
