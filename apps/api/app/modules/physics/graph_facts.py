"""A particle's motion along a line as the question states it, and what follows from it:
physics' reading of a question's words for the graph a reply draws (``services.graph_facts``,
asked by maths' plot through the subject's adapter).

"With acceleration 3.5t m/s². When t = 2 s, P is 10 m from O and has velocity 15 m/s"
(u5-088) writes a(t) and the velocity and the position at one time; "starts from a point A
with velocity 4 m/s ... an acceleration of -1.5t² m/s²" (u5-089) gives them at the start.
The velocity and the displacement are worked out here, by integrating the acceleration
from those stated values: a graph may draw them as formulas the question writes, and a
curve the reply describes is drawn only when it is one of them. A value the question does
not give (no velocity at any time) leaves its formula out, never guessed; so does a
position whose side of O it does not say ("10 m from O").
"""

from __future__ import annotations

import re
from tokenize import TokenError
from typing import Any

from sympy import Expr, Symbol, integrate, nsimplify, simplify
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from app.services.graph_facts import GraphFacts, GraphFormula
from app.services.number_text import count_word_pattern, number_word_value

_T = Symbol("t")
# A number read from its first digit only (never again from inside a digit run: linear).
_NUMBER = r"(?<![\d.])-?\d+(?:\.\d+)?"
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
    rf"\bacceleration\s+(?:is\s+|of\s+)?(?:an?\s+)?(?:constant\s+|uniform\s+)?(?:a\s*=\s*)?"
    rf"(?P<a>{_NUMBER})\s*(?:{_PER_SECOND_SQUARED})"
)
_VELOCITY_IN_T = re.compile(rf"\bvelocity{_SAID}{_IN_T}\s*(?:{_PER_SECOND})")
_VELOCITY = re.compile(rf"\bvelocity{_SAID}(?P<v>{_NUMBER})\s*(?:{_PER_SECOND})")
# A position whose sign is said: a displacement (signed), "s = -3 m" / "x = 4 m", or a
# distance with its side of O ("10 m to the left of O"). "10 m from O" says no side: none.
_POSITION = re.compile(
    rf"\bdisplacement\s+(?:is\s+|of\s+)?(?P<d>{_NUMBER})\s*m\b"
    rf"|\b[sx]\s*=\s*(?P<x>{_NUMBER})\s*m\b"
    rf"|(?P<far>{_NUMBER})\s*m\s+(?:from\s+\w+\s+)?(?P<side>to\s+the\s+(?:right|left)\s+of|"
    r"on\s+the\s+(?:positive|negative)\s+side\s+of|in\s+the\s+(?:positive|negative)\s+direction)"
)
_NEGATIVE_SIDE = re.compile(r"\bleft\b|\bnegative\b")
# The time a clause says its values at: "t = 2", "after 4 s", "after ten seconds"; the
# start ("initially", "starts", "from rest") is t = 0.
_AT_TIME = re.compile(
    rf"\bt\s*=\s*(?P<t>{_NUMBER})|\bat\s+(?P<at>\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?)\b"
    rf"|\bafter\s+(?P<n>\d+(?:\.\d+)?|{count_word_pattern(high=100)})\s*(?:s|secs?|seconds?)\b"
)
_AT_THE_START = re.compile(r"\b(?:starts?|started|starting|initial|initially|from rest)\b")
# A time a clause says for the clauses beside it: "when t = 2 s, ...", "at 3 s ...",
# "initially, ...". A start verb ("starts from O") is its own clause's time alone.
_HEADER = re.compile(r"\binitially\b|\bat\s+the\s+start\b|\bat\s+first\b")
# A sentence that asks: it opens with a verb that asks, a lettered part ("(b) the
# displacement when t = 2 s"), or ends with a question mark. It states nothing.
_ASKED_SENTENCE = re.compile(
    r"^\s*(?:\(?[a-h]\)|find|calculate|determine|work\s+out|show|sketch|draw|plot|what|"
    r"how|state|hence|deduce|evaluate|give)\b|\?\s*$"
)
# Words that make a clause one instant ("initially its acceleration is 3 m/s²", "when at
# rest"), and those that hold a value over the motion ("a constant acceleration", "for 5 s").
_AN_INSTANT = re.compile(
    r"\binitially\b|\binitial\s+acceleration\b|\bwhen\b|\bat\s+the\s+(?:start|instant|moment)\b"
)
_OPENS_AN_INSTANT = re.compile(r"\s*(?:when|whenever|initially|at)\b")
_HELD = re.compile(r"\b(?:constant|uniform|uniformly|steady)\b|\bfor\s+\d")
# A clause that asks, not states: its time is the one asked about ("find its velocity when
# t = 3 s"), and gives none to the clauses beside it.
_ASKED = re.compile(
    r"^\s*(?:find|calculate|determine|work\s+out|show|sketch|draw|plot|what|how|state|"
    r"hence|deduce|evaluate|give)\b"
)
_FROM_REST = re.compile(r"\bfrom rest\b|\bat rest\b")
# An initial state is at t = 0, whatever time the rest of its clause is said at ("starting
# from rest, it has displacement 16 m when t = 2 s", "its initial velocity is 4 m/s"),
# unless its clause names its own ("starts at t = 5 s from rest").
_STARTS_FROM_REST = re.compile(r"\bfrom rest\b")
_INITIAL = re.compile(r"\binitial\s+$")
# Where it starts is where its displacement is measured from: "starts from a point A".
# The displacement named from the start: "its displacement from its starting point".
_FROM_THE_START = re.compile(
    r"\bdisplacement\b[^.;]*?\bfrom\s+(?:its\s+|the\s+)?(?:start(?:ing\s+(?:point|position))?|"
    r"initial\s+position|t\s*=\s*0)\b"
)
# A start verb, and the place it starts at or from: "starts from a point A", "starts from
# rest at O", "moves off from the origin"; "when t = 2 s it is at O" is no start.
# Read in the question's own case: a point is a capital ("from O", "from a point A"), never
# the article "a"; the span after the verb crosses no number (a distance it states).
_STARTS_FROM = re.compile(
    r"\b(?:[Ss]tarts?|[Ss]tarted|[Ss]tarting|[Ss]ets?\s+off|[Mm]oves?|is\s+released|leaves)\b"
    r"[^.;,\d]*?\b(?:at|from)\s+(?!rest\b)(?:the\s+origin|a\s+point\s+[A-Z]\b|[A-Z]\b)"
)
# A distance from a place stated with the start: "starts from rest 10 m from O".
_DISTANCE_FROM = re.compile(rf"{_NUMBER}\s*m\s+from\b")
_SENTENCES = re.compile(r"(?<=[.;!?])\s+")
# A sentence's clauses: each value is said at the time its own clause names, or, naming
# none, at the one the clause before it (else after it) names.
_CLAUSES = re.compile(r",|;|\band\b")
# A clause is cut again where a clause of time opens: "has displacement 16 m | when t = 2 s",
# "with acceleration 2 m/s² | until its velocity is 20 m/s".
_SUBORDINATE = re.compile(r"(?=\b(?:when|whenever|until|till|up\s+to|while|before)\b)")
_OPENS_WHEN = re.compile(r"\s*when(?:ever)?\b")
# A clause of a later state ("until its velocity is 20 m/s", "up to ...", "while ...",
# "before ..."): said at no time it names, it states nothing and lends no time.
_BOUND = re.compile(r"\s*(?:until|till|up\s+to|while|before)\b")
# A duration: "for 4 s", "in ten seconds", from the time the motion starts: 0, or the time
# the question starts it at ("starts at t = 5 s", "from t = 5 s").
_DURATION = re.compile(
    rf"\b(?:for|in)\s+(?P<n>\d+(?:\.\d+)?|{count_word_pattern(high=100)})\s*(?:s|secs?|seconds?)\b"
)
_TIMED_START = re.compile(
    rf"\b(?:starts?|started|starting|sets?\s+off|begins?)\s+at\s+t\s*=\s*(?P<t>{_NUMBER})"
    rf"|\bfrom\s+t\s*=\s*(?P<at>{_NUMBER})"
)
# A second phase of the motion: "then moves with acceleration -1 m/s²", "then decelerates".
_PHASE = re.compile(
    r"\b(?:then|after\s+which|afterwards|followed\s+by)\b[^.;]*?"
    r"\b(?:accelerat\w*|decelerat\w*|retard\w*|brakes?|moves?\s+with|constant\s+(?:speed|velocity))"
)
# "moved through a displacement of 10 m ..., where x is the displacement": x from 0 to 10.
_THROUGH = re.compile(rf"\b(?:through|over)\s+a\s+displacement\s+of\s+(?P<d>{_NUMBER})\s*m\b")
_X_IS_DISPLACEMENT = re.compile(r"\bx\s+is\s+the\s+displacement\b")


_TRANSFORMATIONS = (
    *standard_transformations,
    implicit_multiplication,
    implicit_multiplication_application,
    convert_xor,
)
# The question's symbols in the spelling the reader takes: a minus sign, squares and cubes.
_PLAIN = str.maketrans({"\u2212": "-", "\u00b2": "**2", "\u00b3": "**3", "\u2013": "-"})


def _in_t(text: str) -> Expr | None:
    """An expression in t ("3.5t", "-1.5t**2", "(6 - 2t)"): ``_IN_T`` lets through only
    digits, t, operators and brackets, so nothing else is ever read."""
    try:
        parsed = parse_expr(text.strip(), local_dict={"t": _T}, transformations=_TRANSFORMATIONS)
    except (SyntaxError, TypeError, ValueError, TokenError):
        return None
    if not isinstance(parsed, Expr) or parsed.free_symbols != {_T}:
        return None
    return nsimplify(parsed, rational=True)


def _header_time(clause: str) -> Any | None:
    """The time a clause lends the clauses beside it: one it names ("when t = 2 s", "at 3
    s") or the start it heads ("initially"); never a start verb's ("starts from O")."""
    found = _AT_TIME.search(clause)
    if found is not None:
        return _time(found)
    return 0 if _HEADER.search(clause) else None


# A sentence's clause: lowered, as written, the comma clause it is part of, and whether
# that clause asks.
_Part = tuple[str, str, int, bool]


def _parts(sentence: str) -> list[_Part]:
    """A sentence's clauses, cut at commas, "and" and where a clause of time opens."""
    found: list[_Part] = []
    for index, clause in enumerate(c for c in _CLAUSES.split(sentence) if c.strip()):
        asks = _ASKED.search(clause.lower()) is not None
        found += [(p.lower(), p, index, asks) for p in _SUBORDINATE.split(clause) if p.strip()]
    return found


def _part_time(i: int, parts: list[_Part], lent: list[Any | None]) -> Any | None:
    """The time a clause states its values at: the one it names; else the one a "when"
    clause right after it names ("has displacement 16 m when t = 2 s"); else a start's 0
    ("starts from O"); else the one a header before (else after) it in its sentence lends."""
    lowered, _written, clause, _asks = parts[i]
    own = _AT_TIME.search(lowered)
    if own is not None:
        return _time(own)
    if i + 1 < len(parts):
        following = parts[i + 1]
        if following[2] == clause and _OPENS_WHEN.match(following[0]) and lent[i + 1] is not None:
            return lent[i + 1]
    if _AT_THE_START.search(lowered):
        return 0
    before = [t for t in lent[:i] if t is not None]
    return before[-1] if before else next((t for t in lent[i + 1 :] if t is not None), None)


def _timed_clauses(text: str) -> list[tuple[Any, str, str]]:
    """Each stating clause with the time it says its values at, lowered and as written
    (``_part_time``). A sentence that asks ("Find (a) ..., (b) the displacement when t = 2
    s"), a clause that asks ("find its velocity when t = 3 s") and a clause of a later state
    ("until its velocity is 20 m/s") state nothing and lend no time."""
    timed: list[tuple[Any, str, str]] = []
    for sentence in _SENTENCES.split(text):
        if _ASKED_SENTENCE.search(sentence.lower()):
            continue
        parts = _parts(sentence)
        stating = [not asks and not _BOUND.match(lowered) for lowered, _w, _c, asks in parts]
        lent = [_header_time(p[0]) if ok else None for p, ok in zip(parts, stating, strict=True)]
        for i, (lowered, written, _clause, _asks) in enumerate(parts):
            at = _part_time(i, parts, lent) if stating[i] else None
            if at is not None:
                timed.append((at, lowered, written))
    return timed


def _stated(text: str) -> tuple[list[tuple[Any, Any]], list[tuple[Any, Any]]]:
    """Each velocity and each position the text gives, with the time it gives it at: the
    time its own clause names, or the nearest clause before (or after) it in its sentence
    ("When t = 1 s its velocity is 4 m/s, and when t = 3 s it is 20 m from O": 4 at 1, 20
    at 3; "Initially at rest, after 4 s its velocity is 10 m/s": 0 at 0, 10 at 4)."""
    velocities: list[tuple[Any, Any]] = []
    positions: list[tuple[Any, Any]] = []
    started = False
    measured_from = False
    for at, clause, written in _timed_clauses(text):
        start = at if _AT_TIME.search(clause) else 0
        velocities += [
            (
                start if _INITIAL.search(clause[: m.start()]) else at,
                nsimplify(m.group("v"), rational=True),
            )
            for m in _VELOCITY.finditer(clause)
        ]
        if _FROM_REST.search(clause):
            velocities.append((start if _STARTS_FROM_REST.search(clause) else at, 0))
        positions += [
            (start if _INITIAL.search(clause[: match.start()]) else at, value)
            for match in _POSITION.finditer(clause)
            if (value := _signed(match)) is not None
        ]
        started = started or (at == 0 and _STARTS_FROM.search(written) is not None)
        measured_from = measured_from or (at == 0 and _DISTANCE_FROM.search(clause) is not None)
    # Its displacement is measured from where it starts, when the question names that place
    # (O, the origin, a point A) or the displacement from the start, and states no position:
    # "initially" or "from rest" says nothing of where it is, nor does a start some
    # distance from O ("starts from rest 10 m from O": its side unsaid).
    starts_at_its_place = started or _FROM_THE_START.search(text.lower()) is not None
    if starts_at_its_place and not positions and not measured_from:
        positions.append((0, 0))
    return velocities, positions


def _signed(match: re.Match[str]) -> Any | None:
    """A position with its sign: a displacement or "s =" as written, a distance from O
    negative on its left or negative side."""
    if match.group("far") is not None:
        far = nsimplify(match.group("far"), rational=True)
        return -far if _NEGATIVE_SIDE.search(match.group("side")) else far
    written = match.group("d") or match.group("x")
    return None if written is None else nsimplify(written, rational=True)


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
    """A constant acceleration ("starts from rest with acceleration 2 m/s²"), said in a
    clause that names no instant: "when t = 2 its acceleration is 3 m/s²", "initially its
    acceleration is 3 m/s²" and "when at rest, its acceleration is 2 m/s²" are values at one
    time, not a(t), unless the clause says it is constant or for how long."""
    for sentence in _SENTENCES.split(lowered):
        clauses = [c for c in _CLAUSES.split(sentence) if c.strip()]
        for i, clause in enumerate(clauses):
            found = _CONSTANT_ACCELERATION.search(clause)
            if found is None:
                continue
            # A clause opening the sentence says when the next one holds ("When at rest, its
            # acceleration is 2 m/s²").
            leading = clauses[i - 1] if i > 0 and _OPENS_AN_INSTANT.match(clauses[i - 1]) else ""
            instant = any(
                _AT_TIME.search(part) or _AN_INSTANT.search(part) for part in (clause, leading)
            )
            if _HELD.search(clause) is not None or not instant:
                return nsimplify(found.group("a"), rational=True)
    return None


def _holds(velocity: Expr, acceleration: Expr | None, stated: list[tuple[Any, Any]]) -> bool:
    """A velocity the question writes agrees with every velocity it states at a time, and
    with its acceleration: "at rest at t = 2 s, then moves with velocity 2t m/s" does not."""
    if any(simplify(velocity.subs(_T, at) - value) != 0 for at, value in stated):
        return False
    return acceleration is None or simplify(velocity.diff(_T) - acceleration) == 0


def _phases(lowered: str) -> bool:
    """The motion changes: two accelerations it states ("2 m/s² for 3 s, then -1 m/s² for
    4 s"), or a phase after its first ("then decelerates")."""
    stated = {e for m in _ACCELERATION.finditer(lowered) if (e := _in_t(m.group("expr")))}
    stated |= {
        nsimplify(m.group("a"), rational=True) for m in _CONSTANT_ACCELERATION.finditer(lowered)
    }
    return len(stated) > 1 or _PHASE.search(lowered) is not None


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
    if _phases(lowered):
        return []  # a motion in phases is a curve in pieces: none, rather than a wrong one
    velocities, positions = _stated(text)
    if velocity is not None and not _holds(velocity, acceleration, velocities):
        return []  # a written v(t) the stated values or a(t) contradict: no motion
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
    groups = match.groupdict()
    for name in ("t", "at"):
        if groups.get(name) is not None:
            return nsimplify(groups[name], rational=True)
    word = match.group("n")
    value = number_word_value(word) if not word[0].isdigit() else nsimplify(word, rational=True)
    return None if value is None else nsimplify(value, rational=True)


def motion_interval(text: str) -> tuple[str, Any, Any] | None:
    """The interval the motion is asked about, (letter, start, end): from its start (or the
    first time it names) to the last time it names, for a particle whose motion it states
    in one phase (u5-089's "after ten seconds" from the start); x from 0 to the displacement
    a force moves it through ("through a displacement of 10 m", u5-087)."""
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
    if _phases(lowered):
        return None  # a motion in phases: no formula, so no stretch of one
    times = [t for m in _AT_TIME.finditer(lowered) if (t := _time(m)) is not None]
    # Its start: the time the question starts it at ("starts at t = 5 s"), else 0; a time a
    # value is stated at ("when t = 2 s its velocity is 15 m/s") is no start.
    timed = _TIMED_START.search(lowered)
    start = _time(timed) if timed is not None else 0
    if timed is not None or _AT_THE_START.search(lowered):
        times.append(start)
    # A duration runs from that start: "for 4 s" is [0, 4], "from t = 2 s ... for 4 s" [2, 6].
    durations = [d for m in _DURATION.finditer(lowered) if (d := _time(m)) is not None]
    if durations:
        times += [start, start + max(durations)]
    if len(set(times)) < 2:
        return None
    return "t", min(times), max(times)


def read_graph_facts(text: str) -> GraphFacts:
    """Physics' reader for maths' plot (``services.graph_facts``): the motion's formulas in
    t and the interval it is asked about, as SymPy text. Runs in the SymPy pool. The text
    keeps its case: a point is a capital letter."""
    readable = text.translate(_PLAIN)
    formulas = tuple(
        GraphFormula(name, str(expr), unit) for name, expr, unit in motion_formulas(readable)
    )
    found = motion_interval(readable)
    if found is None:
        return GraphFacts(formulas)
    letter, low, high = found
    return GraphFacts(formulas, (str(low), str(high)), letter)
