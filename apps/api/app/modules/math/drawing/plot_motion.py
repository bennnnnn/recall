"""A particle's motion along a line as the question states it, and what follows from it.

"With acceleration 3.5t m/s². When t = 2 s, P is 10 m from O and has velocity 15 m/s"
(u5-088) writes a(t) and the velocity and the position at one time; "starts from a point A
with velocity 4 m/s ... an acceleration of -1.5t² m/s²" (u5-089) gives them at the start.
The velocity and the displacement are worked out here, by integrating the acceleration
from those stated values: a graph may draw them as formulas the question writes, and a
curve the reply describes is drawn only when it is one of them. A value the question does
not give (no velocity at any time) leaves its formula out, never guessed.
"""

from __future__ import annotations

import re
from typing import Any

from sympy import Expr, Symbol, integrate, nsimplify

from app.modules.math.tool_check import parse_formula
from app.services.number_text import count_word_pattern, number_word_value

_T = Symbol("t")
_NUMBER = r"-?\d+(?:\.\d+)?"
# The units of an acceleration and of a velocity, as plain text writes them: "m/s**2",
# "m s^-2", "ms^-2"; "m/s", "m s^-1", "ms^-1".
_PER_SECOND_SQUARED = r"m\s*/\s*s(?:\^|\*\*)2|m\s*s(?:\^|\*\*)-2|ms(?:\^|\*\*)-2"
_PER_SECOND = r"m\s*/\s*s(?![*^])|m\s*s(?:\^|\*\*)-1|ms(?:\^|\*\*)-1"
# An expression in t, before its unit: "3.5t", "-1.5t**2", "(3t**2 - 2t)".
_IN_T = r"(?P<expr>[-+]?[0-9.t*/^()+\- ]*?t[0-9.t*/^()+\- ]*?)"
_SAID = r"\s+(?:is\s+|of\s+)?(?:[av]\s*=\s*)?"
_ACCELERATION = re.compile(rf"\bacceleration{_SAID}{_IN_T}\s*(?:{_PER_SECOND_SQUARED})")
# A constant acceleration: "with acceleration 2 m/s²", said at no time.
_CONSTANT_ACCELERATION = re.compile(
    rf"\bacceleration{_SAID}(?P<a>{_NUMBER})\s*(?:{_PER_SECOND_SQUARED})"
)
_VELOCITY_IN_T = re.compile(rf"\bvelocity{_SAID}{_IN_T}\s*(?:{_PER_SECOND})")
_VELOCITY = re.compile(rf"\bvelocity{_SAID}(?P<v>{_NUMBER})\s*(?:{_PER_SECOND})")
_POSITION = re.compile(
    rf"(?P<x>{_NUMBER})\s*m\s+from\s+\w+|\bdisplacement\s+(?:is\s+|of\s+)?(?P<d>{_NUMBER})\s*m\b"
)
# The time a clause says its values at: "t = 2", "after 4 s", "after ten seconds"; the
# start ("initially", "starts", "from rest") is t = 0.
_AT_TIME = re.compile(
    rf"\bt\s*=\s*(?P<t>{_NUMBER})|\bafter\s+(?P<n>\d+(?:\.\d+)?|{count_word_pattern(high=100)})"
    r"\s*(?:s|secs?|seconds?)\b"
)
_AT_THE_START = re.compile(r"\b(?:starts?|started|starting|initially|from rest)\b")
_FROM_REST = re.compile(r"\bfrom rest\b|\bat rest\b")
# Where it starts is where its displacement is measured from: "starts from a point A".
_STARTS_FROM = re.compile(
    r"\bstarts?\s+from\s+(?!rest\b)(?:a\s+point\s+\w+|the\s+origin|\w+)\b|\bat\s+the\s+origin\b"
)
_SENTENCES = re.compile(r"(?<=[.;!?])\s+")
# A sentence's clauses: each value is said at the time its own clause names, or, naming
# none, at the one the clause before it (else after it) names.
_CLAUSES = re.compile(r",|;|\band\b")
# A time it names: "t = 5", "after ten seconds", "for 4 s".
_TIME = re.compile(
    rf"\bt\s*=\s*(?P<t>{_NUMBER})|\b(?:after|for|in)\s+(?P<n>\d+(?:\.\d+)?|{count_word_pattern(high=100)})"
    r"\s*(?:s|secs?|seconds?)\b"
)
# "moved through a displacement of 10 m ..., where x is the displacement": x from 0 to 10.
_THROUGH = re.compile(rf"\b(?:through|over)\s+a\s+displacement\s+of\s+(?P<d>{_NUMBER})\s*m\b")
_X_IS_DISPLACEMENT = re.compile(r"\bx\s+is\s+the\s+displacement\b")


def _in_t(text: str) -> Expr | None:
    parsed = parse_formula(text.strip())
    if not isinstance(parsed, Expr) or parsed.free_symbols != {_T}:
        return None
    return nsimplify(parsed, rational=True)


def _clause_time(clause: str) -> Any | None:
    found = _AT_TIME.search(clause)
    if found is not None:
        return _time(found)
    return 0 if _AT_THE_START.search(clause) else None


def _timed_clauses(text: str) -> list[tuple[Any, str]]:
    """Each clause with the time it says its values at: its own, or the clause before's
    within the sentence (else the one after); a clause of a sentence naming no time, none."""
    timed: list[tuple[Any, str]] = []
    for sentence in _SENTENCES.split(text.lower()):
        clauses = [c for c in _CLAUSES.split(sentence) if c.strip()]
        times = [_clause_time(c) for c in clauses]
        for i, clause in enumerate(clauses):
            before = [t for t in times[: i + 1] if t is not None]
            after = [t for t in times[i + 1 :] if t is not None]
            at = before[-1] if before else (after[0] if after else None)
            if at is not None:
                timed.append((at, clause))
    return timed


def _stated(text: str) -> tuple[list[tuple[Any, Any]], list[tuple[Any, Any]]]:
    """Each velocity and each position the text gives, with the time it gives it at: the
    time its own clause names, or the nearest clause before (or after) it in its sentence
    ("When t = 1 s its velocity is 4 m/s, and when t = 3 s it is 20 m from O": 4 at 1, 20
    at 3; "Initially at rest, after 4 s its velocity is 10 m/s": 0 at 0, 10 at 4)."""
    velocities: list[tuple[Any, Any]] = []
    positions: list[tuple[Any, Any]] = []
    started = False
    for at, clause in _timed_clauses(text):
        velocities += [
            (at, nsimplify(m.group("v"), rational=True)) for m in _VELOCITY.finditer(clause)
        ]
        if _FROM_REST.search(clause):
            velocities.append((at, 0))
        for match in _POSITION.finditer(clause):
            positions.append((at, nsimplify(match.group("x") or match.group("d"), rational=True)))
        start = _STARTS_FROM.search(clause) or _AT_THE_START.search(clause)
        started = started or (at == 0 and start is not None)
    # Its displacement is measured from where it starts, when no position is stated.
    if started and not positions:
        positions.append((0, 0))
    return velocities, positions


def _through(rate: Expr, stated: list[tuple[Any, Any]]) -> Expr | None:
    """The function whose rate is ``rate`` and whose value is the one stated, when the
    question states one value (two that disagree are no motion)."""
    if not stated:
        return None
    found = integrate(rate, _T)
    at, value = stated[0]
    found = found + value - found.subs(_T, at)
    if any(found.subs(_T, t) != v for t, v in stated[1:]):
        return None
    return found


def _constant_acceleration(lowered: str) -> Expr | None:
    """A constant acceleration ("with acceleration 2 m/s²"), said in a clause that names
    no time: "when t = 2 its acceleration is 3 m/s²" is a value at one time, not a(t)."""
    for clause in _CLAUSES.split(lowered):
        found = _CONSTANT_ACCELERATION.search(clause)
        if found is not None and _AT_TIME.search(clause) is None:
            return nsimplify(found.group("a"), rational=True)
    return None


def motion_formulas(text: str) -> list[tuple[str, Expr, str]]:
    """The motion's formulas in t, (name, formula, unit): the acceleration it writes, and
    the velocity and the displacement worked out from the values it states."""
    lowered = text.lower()
    acceleration = next(
        (e for m in _ACCELERATION.finditer(lowered) if (e := _in_t(m.group("expr")))), None
    )
    if acceleration is None:
        acceleration = _constant_acceleration(lowered)
    velocity = next(
        (e for m in _VELOCITY_IN_T.finditer(lowered) if (e := _in_t(m.group("expr")))), None
    )
    if acceleration is None and velocity is None:
        return []
    velocities, positions = _stated(text)
    found: list[tuple[str, Expr, str]] = []
    if acceleration is not None:
        found.append(("a", acceleration, "m/s**2"))
        velocity = velocity or _through(acceleration, velocities)
    if velocity is not None:
        found.append(("v", velocity, "m/s"))
        displacement = _through(velocity, positions)
        if displacement is not None:
            found.append(("s", displacement, "m"))
    return found


def _time(match: re.Match[str]) -> Any | None:
    if match.group("t") is not None:
        return nsimplify(match.group("t"), rational=True)
    word = match.group("n")
    value = number_word_value(word) if not word[0].isdigit() else nsimplify(word, rational=True)
    return None if value is None else nsimplify(value, rational=True)


def motion_interval(text: str) -> tuple[str, Any, Any] | None:
    """The interval the motion is asked about, (letter, start, end): from its start (or the
    first time it names) to the last time it names, for a particle whose motion it states
    (u5-089's "after ten seconds" from the start); x from 0 to the displacement a force
    moves it through ("through a displacement of 10 m", u5-087)."""
    lowered = text.lower()
    through = _THROUGH.search(lowered)
    if through is not None and _X_IS_DISPLACEMENT.search(lowered):
        return "x", 0, nsimplify(through.group("d"), rational=True)
    if not (
        _ACCELERATION.search(lowered)
        or _VELOCITY_IN_T.search(lowered)
        or _constant_acceleration(lowered) is not None
    ):
        return None  # no motion stated
    times = [t for m in _TIME.finditer(lowered) if (t := _time(m)) is not None]
    if _AT_THE_START.search(lowered):
        times.append(0)
    if len(set(times)) < 2:
        return None
    return "t", min(times), max(times)
