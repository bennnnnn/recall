"""The conversation's latest subject, for a line that leans on the ones before it.

"Draw it", "3", "the area" and "do it properly" name nothing of their own: each is about
the subject the user brought up last. Walking back through the user's lines passes over
such lines and stops at the newest line with a subject of its own, which is the latest
subject. Nothing older is ever reached, so a line about something else in between always
ends the walk. Live (2026-11-09), "Draw it" after a triangle walked past "Do it properly",
"The area", "3" and the triangle itself and drew sin(x²)cos(x²) from six messages back.

The lines passed over that add to the subject join it: a number after an open list of them
("Triangle with sides 5, 4," then "3") completes the setup, and a quantity asked of it
("the area") is its question. "Do it properly", "thanks" and "draw it" add nothing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.modules.turn_reading.routing import is_lightweight_chat_turn
from app.services.text_normalize import collapse_ws

# A lone unknown or value: ``x``, ``$\theta$``, ``5``, ``-2.5``, ``for y``.
_FRAGMENT = re.compile(
    r"(?:for\s+)?(?:[a-z\u03b1-\u03c9]|\\[a-z]+|[-+\u2212]?\d+(?:\.\d+)?)\s*[.?!]?",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"[-+\u2212]?\d+(?:\.\d+)?")
# A setup left open on a list of numbers: "sides 5, 4,", "sides 5, 4 and", "3 by".
_OPEN_LIST = re.compile(r"\d\s*(?:,|&|\band|\bby)\s*$", re.IGNORECASE)
# A number or a sign of maths: the line states something of its own.
_OWN_MATTER = re.compile(r"[\d=^+*/<>()\[\]{}$\\]")
_WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")
_EDGES = " \t\n.,;:!?\"'`"
# More words than a line that only points back needs.
_MAX_WORDS = 6

# What points at the subject.
_POINTERS = frozenset({"it", "this", "that", "them", "these", "those"})
# Words that say nothing about what is meant: the frame of a request, its politeness, how
# much and how well.
_FRAME = frozenset(
    """a an the and or but so ok okay now then also too please pls plz can could would will
    you u me us i my for to of with in on at by about again once more just how why what whats
    what's is are was do does did done properly correctly clearly fully full simply step out
    through up over instead way one another next let lets let's yes yeah yep no nope sure cool
    nice great awesome perfect got thanks thank thx""".split()
)
# What a request does to the subject, and the work it asks for.
_ACTS = frozenset(
    """redo draw graph plot sketch show visualize visualise chart picture explain solve work
    working check try make give tell go continue finish repeat write label simplify factor
    factorise factorize expand integrate differentiate derive steps solution answer method
    diagram figure drawing result example examples proof prove hint""".split()
)
# What a problem asks for: "the area", "its perimeter", "what about the angles".
_MEASURES = (
    r"area|perimeter|circumference|diameter|radius|radii|volume|hypotenuse|angle|height|length"
    r"|width|base|side|diagonal|slope|gradient|intercept|root|zero|vertex|vertices|derivative"
    r"|integral|speed|velocity|acceleration|distance|displacement|force|energy|momentum|mass"
    r"|weight|range|mean|median|mode|average|sum|total|product|probability|value"
)
_ASK_LEAD = (
    r"(?:and|so|ok|okay|now|then|also|great|cool|what about|how about|what's|whats|what is"
    r"|what are|find|calculate|compute|give me|tell me|i need|i want)"
)
_MEASURE_ASK = re.compile(
    rf"(?:{_ASK_LEAD} )*(?:the|its|their) (?:[a-z]+ )?(?:{_MEASURES})(?:s|es)?"
    r"(?: (?:please|pls|too|then|now))?"
)


def is_fragment(text: str) -> bool:
    """A lone number or letter (``5``, ``x``, ``for x``): part of the open problem, not one."""
    cleaned = " ".join(text.strip().strip("$").split())
    return bool(_FRAGMENT.fullmatch(cleaned))


def _plain(line: str) -> str:
    return collapse_ws(line).lower().strip(_EDGES)


def _asks_a_measure(plain: str) -> bool:
    return _MEASURE_ASK.fullmatch(" ".join(_WORD.findall(plain))) is not None


def leans_on_earlier(line: str) -> bool:
    """A line with no subject of its own: a fragment, small talk, a quantity asked of the
    subject ("the area"), or a request that points at it ("draw it", "do it properly")."""
    plain = _plain(line)
    if not plain or is_fragment(plain) or is_lightweight_chat_turn(plain):
        return True
    if _OWN_MATTER.search(plain):
        return False
    words = _WORD.findall(plain)
    if len(words) > _MAX_WORDS:
        return False
    if _asks_a_measure(plain):
        return True
    # "Translate it to French" and "is that fast for a car?" say what they are about.
    own = [word for word in words if word not in _FRAME | _POINTERS | _ACTS]
    if any(word in _POINTERS for word in words):
        return len(own) <= 1
    return not own


@dataclass(frozen=True)
class LatestSubject:
    """The newest line with a subject of its own, completed by the lines after it."""

    # The line, with any number that completes its open list: what a figure is drawn from.
    setup: str
    # The quantity asked of it last ("The area"); "and the perimeter?" after it asks anew.
    ask: str | None = None

    @property
    def problem(self) -> str:
        """The setup with its question: "Triangle are with sides 5, 4, 3. The area"."""
        if self.ask is None:
            return self.setup
        setup = self.setup.rstrip(" ,;:")
        lead = setup if setup.endswith((".", "?", "!")) else f"{setup}."
        return f"{lead} {self.ask}"


def latest_subject(user_lines: Sequence[str]) -> LatestSubject | None:
    """The conversation's latest subject from the user's lines, oldest first; None when
    every line leans on an earlier one."""
    leaning: list[str] = []
    for line in reversed(user_lines):
        if leans_on_earlier(line):
            leaning.append(line)
            continue
        return _completed(line, reversed(leaning))
    return None


def adds_to_subject(line: str) -> bool:
    """A lone number or a quantity asked ("3", "the area"): a line that adds to the latest
    subject, where "draw it" or "do it properly" only points at it."""
    plain = _plain(line)
    return _NUMBER.fullmatch(plain.strip("$")) is not None or _asks_a_measure(plain)


def continued_subject(line: str, earlier: Sequence[str]) -> str | None:
    """The latest subject whole once ``line`` adds to it: "3" after "Triangle are with sides
    5, 4," is "Triangle are with sides 5, 4, 3", and "The area" after that asks its area.
    None when the line adds nothing ("draw it", "thanks") or has a subject of its own."""
    if not leans_on_earlier(line):
        return None
    before = latest_subject(earlier)
    after = latest_subject([*earlier, line])
    if before is None or after is None or after.problem == before.problem:
        return None
    return after.problem


def _completed(setup: str, later: Iterable[str]) -> LatestSubject:
    ask: str | None = None
    for line in later:
        plain = collapse_ws(line).strip(_EDGES + "$")
        if _NUMBER.fullmatch(plain) and _OPEN_LIST.search(setup):
            setup = f"{setup.rstrip()} {plain}"
        elif _asks_a_measure(_plain(line)):
            ask = collapse_ws(line)
    return LatestSubject(setup, ask)


# "Draw it", "graph this", "can you plot that please": a request to see the subject.
_SEE_VERBS = ("graph", "plot", "sketch", "draw", "visualize", "visualise", "chart")
_POLITE_PREFIXES = ("please ", "can you ", "could you ")
# The objects that name nothing: the subject is the chat's latest.
_PRONOUN_OBJECTS = frozenset({"", "it", "this", "that"})


def _without_politeness(lower: str) -> str:
    text = lower
    changed = True
    while changed:
        changed = False
        if text.startswith("please "):
            text = text[7:].strip()
            changed = True
        if text.endswith(" please"):
            text = text[:-7].strip()
            changed = True
        for prefix in _POLITE_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
                changed = True
                break
    return text


def see_request_object(line: str) -> str | None:
    """What a request to see names: "" for the verb alone ("Plot"), "it" for "draw it",
    "the curve" for "graph the curve"; None for a line that is no such request."""
    lower = _without_politeness(collapse_ws(line).lower().rstrip(".!?"))
    for verb in _SEE_VERBS:
        if lower == verb:
            return ""
        if lower.startswith(f"{verb} "):
            return lower[len(verb) + 1 :].strip()
    return None


def asks_to_see(line: str) -> bool:
    """ "Draw it", "graph this", "Plot": the latest subject, drawn by the subject it is."""
    return see_request_object(line) in _PRONOUN_OBJECTS
