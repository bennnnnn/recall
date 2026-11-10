"""A line that adds to the open problem: "3" after "Triangle with sides 5, 4,", "the area".

Live (2026-11-09) neither "3" nor "The area" was ever solved: alone they are no problem.
They join the problem the exchange before them is about, by the exchange's shape and not
by guessing the subject from words:

- a lone number completes a setup left open on a list of numbers ("sides 5, 4,") when the
  reply after that setup asked for something ("What's the third side length?");
- a quantity asked of it ("the area", "and its perimeter?") is its new question when the
  reply before did not end on a question. After one, or in a lesson, the line answers it:
  "the hypotenuse" to "Which side is the longest?" is a quiz answer, never a problem.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.modules.turn_reading.lesson_flow import lesson_step
from app.modules.turn_reading.routing import EMOJI
from app.services.text_normalize import collapse_ws

# A lone unknown or value: ``x``, ``$\theta$``, ``5``, ``-2.5``, ``for y``.
_FRAGMENT = re.compile(
    r"(?:for\s+)?(?:[a-z\u03b1-\u03c9]|\\[a-z]+|[-+\u2212]?\d+(?:\.\d+)?)\s*[.?!]?",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"[-+\u2212]?\d+(?:\.\d+)?")
# A setup left open on a list of numbers: "sides 5, 4,", "sides 5, 4 and", "3 by".
_OPEN_LIST = re.compile(r"\d\s*(?:,|&|\band|\bby)\s*$", re.IGNORECASE)
_WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")
_EDGES = " \t\n.,;:!?\"'`"
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
_TRAILING_MARKS = " \t*_~)"


def is_fragment(text: str) -> bool:
    """A lone number or letter (``5``, ``x``, ``for x``): part of the open problem, not one."""
    cleaned = " ".join(text.strip().strip("$").split())
    return bool(_FRAGMENT.fullmatch(cleaned))


def _plain(line: str) -> str:
    return collapse_ws(line).lower().strip(_EDGES + "$")


def _asks_a_measure(plain: str) -> bool:
    # The quantity words are English: a line in another script asks none of them.
    if any(char.isalpha() and not char.isascii() for char in plain):
        return False
    return _MEASURE_ASK.fullmatch(" ".join(_WORD.findall(plain))) is not None


def adds_to_problem(line: str) -> bool:
    """A lone number or a quantity asked ("3", "the area"): a line that can add to the open
    problem, where "draw it" or "do it properly" only points at it."""
    plain = _plain(line)
    return _NUMBER.fullmatch(plain) is not None or _asks_a_measure(plain)


@dataclass(frozen=True)
class Problem:
    """A problem the user stated, completed by the lines that added to it."""

    # The line, with any number that completes its open list: what a figure is drawn from.
    setup: str
    # The quantity asked of it last ("The area"); "and the perimeter?" after it asks anew.
    ask: str | None = None

    @property
    def text(self) -> str:
        """The setup with its question: "Triangle are with sides 5, 4, 3. The area"."""
        if self.ask is None:
            return self.setup
        setup = self.setup.rstrip(" ,;:")
        lead = setup if setup.endswith((".", "?", "!")) else f"{setup}."
        return f"{lead} {self.ask}"


def _ends_on_a_question(reply: str) -> bool:
    """The reply ends on a question, as a quiz does: the next line answers it."""
    lines = [line for line in reply.strip().splitlines() if line.strip()]
    last = EMOJI.sub("", lines[-1]).rstrip(_TRAILING_MARKS) if lines else ""
    return last.endswith("?")


def _asks(reply: str) -> bool:
    """The reply's last paragraph asks something ("What's the third side length? 🔺", "Did
    you mean the third side? Send it and I'll work it out.")."""
    return "?" in reply.strip().split("\n\n")[-1]


def _joined(exchanges: Sequence[tuple[str, str]], index: int) -> Problem | None:
    """The problem the user line at ``index`` adds to, with it; None when it adds to none."""
    if index < 2 or exchanges[index - 1][0] != "assistant" or exchanges[index - 2][0] != "user":
        return None
    reply = exchanges[index - 1][1]
    if lesson_step(reply) is not None:
        return None
    plain = _plain(exchanges[index][1])
    if _NUMBER.fullmatch(plain):
        base = _problem_of(exchanges, index - 2)
        if not _asks(reply) or _OPEN_LIST.search(base.setup) is None:
            return None
        return replace(base, setup=f"{base.setup.rstrip()} {plain}")
    if _asks_a_measure(plain) and not _ends_on_a_question(reply):
        return replace(_problem_of(exchanges, index - 2), ask=collapse_ws(exchanges[index][1]))
    return None


def _problem_of(exchanges: Sequence[tuple[str, str]], index: int) -> Problem:
    return _joined(exchanges, index) or Problem(exchanges[index][1])


def problem_at(exchanges: Sequence[tuple[str, str]], index: int) -> Problem:
    """The problem the user line at ``index`` is part of, whole: the lines it added to before
    it, and the lines that added to it after ("Triangle are with sides 5, 4," then "3")."""
    problem = _problem_of(exchanges, index)
    later = index + 2
    while later < len(exchanges) and exchanges[later][0] == "user":
        joined = _joined(exchanges, later)
        if joined is None:
            break
        problem, later = joined, later + 2
    return problem


def continued_problem_text(line: str, earlier: Sequence[tuple[str, str]]) -> str | None:
    """The open problem ``line`` adds to, whole: "3" after "Triangle are with sides 5, 4,"
    and the reply asking for the third side is "Triangle are with sides 5, 4, 3"."""
    exchanges = [*earlier, ("user", line)]
    joined = _joined(exchanges, len(exchanges) - 1)
    return None if joined is None else joined.text
