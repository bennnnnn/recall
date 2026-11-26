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

from app.services.rounding_rule import precision_only

# A verb of giving or showing, then the answer as its object: "give your answer", "write
# the result", "round it", "show all working", "explain your answers".
_ORDER_ON_THE_ANSWER = re.compile(
    r"^\s*(?:please\s+)?(?:(?:and|then|now)\s+)?"
    r"(?:give|write|express|state|leave|present|quote|round|show|explain|justify)\s+"
    r"(?:(?:your|the|each|all|both|this|that|these|those)\s+)?(?:final\s+)?"
    r"(?:answers?|results?|values?|working|workings|work|steps|it|them)\b",
    re.IGNORECASE,
)


def orders_the_answer(clause: str) -> bool:
    """The clause only says how the answer before it is given (the module docstring)."""
    return _ORDER_ON_THE_ANSWER.match(clause) is not None or precision_only(clause) is not None
