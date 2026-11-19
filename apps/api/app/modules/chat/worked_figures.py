"""How a worked answer's card shows its number: the one rule every card follows.

The working ends on its value unrounded and the card rounds it once (the owner's rule,
2026-11-13), by ``services.answer_number`` (2026-11-18: two decimal places, whole numbers
whole, a power of ten only past 10⁹ or below 0.001), or to the precision the question asks.
A sum of money is exact to the cent as written, and a value in symbols or words is no
number to round.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.services.answer_number import Precision, number_latex
from app.services.school_rounding import MOST_DIGITS

if TYPE_CHECKING:
    from app.modules.chat.worked_solution import Answer

# A number written plainly: "29.008", "-4", "0.31".
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
# A pH, pOH or pK: its decimals are the figures of the concentration it came from.
_LOGARITHM = re.compile(r"^\s*(?:\\mathrm\{)?p(?:H|OH|K[ab]?)\b")
# A note that only names a precision: "to 2 s.f.", "3 d.p.", "to 3 significant figures".
_PRECISION_NOTE = re.compile(
    r"^\s*(?:to\s+)?\d+\s*(?:s\.?\s*f\.?|d\.?\s*p\.?|significant\s+figures?|decimal\s+places?)\s*$",
    re.IGNORECASE,
)


def card_answer(answer: Answer, asked: tuple[int, int] = (0, -1)) -> Answer:
    """``answer`` with its value by the rule, or to the precision the question asks
    (``asked``: significant figures, decimal places, as ``school_rounding.asked_rounding``
    reads them; 0 and -1 for none). A note that only named a precision goes: the card says
    the precision it shows."""
    from app.services.subjects.registry import MONEY

    shown = answer.value.strip()
    if not _NUMBER.fullmatch(shown) or MONEY.names_currency(answer.unit or ""):
        return answer  # a sum of money is exact to the cent: $12.34 is never $12.3
    if _LOGARITHM.match(answer.symbol or ""):
        return answer  # a pH's decimals are its concentration's figures
    figures, places = (min(count, MOST_DIGITS) for count in asked)
    value = number_latex(float(shown), Precision(figures=figures, places=places))
    note = "" if _PRECISION_NOTE.match(answer.note or "") else answer.note
    return answer.model_copy(update={"value": value, "note": note})
