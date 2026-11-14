"""A line that adds to an open problem: "3" after "Triangle with sides 5, 4,", "the area".

Live (2026-11-09) neither "3" nor "The area" was ever solved: alone they are no problem.
Whether a short line continues a problem, and which, is a model's read (``chat.
referent_read``): a rule on the reply's last line refused "the area" after "What would you
like to find: the area or the perimeter?" and joined a quiz answer after an encouraging
paragraph. Once a problem is named, its pieces join by their shape alone: a lone number
completes a setup left open on a list of numbers ("sides 5, 4,"), and a quantity asked of
it ("the area", "and its perimeter?") is its question.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.services.text_normalize import collapse_ws

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


def _joined(exchanges: Sequence[tuple[str, str]], index: int) -> Problem | None:
    """The problem the user line at ``index`` adds to, with it, by its shape; None when it
    is no piece of the problem before it."""
    if index < 2 or exchanges[index - 1][0] != "assistant" or exchanges[index - 2][0] != "user":
        return None
    return continue_problem(_problem_of(exchanges, index - 2), exchanges[index][1])


def continue_problem(problem: Problem, line: str) -> Problem | None:
    """``problem`` with ``line`` added: a number completing its open list, or a quantity
    asked of it; None when the line is neither."""
    plain = _plain(line)
    if _NUMBER.fullmatch(plain):
        if _OPEN_LIST.search(problem.setup) is None:
            return None
        return replace(problem, setup=f"{problem.setup.rstrip()} {plain}")
    if _asks_a_measure(plain):
        return replace(problem, ask=collapse_ws(line))
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
