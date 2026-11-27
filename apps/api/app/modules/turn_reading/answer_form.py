"""An order about the answer itself: how it is given, never a question of its own.

"What speed is he walking at? Give your answer in metres per second." asks one thing; its
second sentence says the unit to answer in. Planned as a request of its own, the reply
worked two parts and carded the first, 300 ft/min, in the unit the question said not to use
(textbook round, 2026-11-26). An order whose object is the answer (its unit, its precision,
its form, its working, its reasons) qualifies the question before it: "Give the answer to
the correct number of significant figures", "Express it in standard form", "Show your
working", "Explain your answer", and a precision said alone ("To 3 s.f.").
"""

from __future__ import annotations

import re

from app.services.number_text import count_word_pattern
from app.services.rounding_rule import precision_only


def _answer_orders() -> tuple[re.Pattern[str], re.Pattern[str]]:
    """The two orders about the answer, built from their shared pieces (kept local: they are
    pattern pieces, not rule text the prompt counts)."""
    opening = r"^\s*(?:please\s+)?(?:(?:and|then|now)\s+)?"
    its = r"(?:(?:your|the|each|all|both|this|that|these|those)\s+)?(?:final\s+)?"
    ending = r"\s*[.!?]*\s*$"
    # After the answer only a unit, a form or a precision: "in m/s", "as a fraction", "to 3
    # s.f."; "to reset my router" is a request of its own (review of #2604).
    form = (
        r"(?:\s+(?:in\s+\S+(?:\s+\S+){0,3}|as\s+\S+(?:\s+\S+){0,2}"
        rf"|(?:correct\s+)?to\s+(?:\d+|{count_word_pattern(low=1, high=12)}|the\s+nearest"
        r"|the\s+correct|an?\s+(?:appropriate|suitable|sensible))\b[^.!?\n]*))?"
    )
    # Giving the answer in a form: "give your answer in m/s", "express it in standard form",
    # "write the result as a fraction", "round it to 1 dp", "give your answer.".
    gives = re.compile(
        rf"{opening}(?:give|write|express|state|leave|present|quote|round|report)\s+"
        rf"{its}(?:answers?|results?|values?|it|them)\b{form}{ending}",
        re.IGNORECASE,
    )
    # Showing how it was found, and nothing more: "show your working", "explain your answer".
    shows = re.compile(
        rf"{opening}(?:show|explain|justify)\s+{its}(?:working|workings|work|steps|reasoning"
        rf"|answers?){ending}",
        re.IGNORECASE,
    )
    return gives, shows


_GIVES_THE_ANSWER, _SHOWS_THE_WORKING = _answer_orders()


def orders_the_answer(clause: str) -> bool:
    """The clause only says how the answer before it is given (the module docstring)."""
    return (
        _GIVES_THE_ANSWER.match(clause) is not None
        or _SHOWS_THE_WORKING.match(clause) is not None
        or precision_only(clause) is not None
    )
