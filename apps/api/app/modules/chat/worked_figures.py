"""How many figures a physics worked answer's card keeps: at most three, rounded once.

The working ends on its value unrounded and the card rounds it once (the owner's rule,
2026-11-13). A measured quantity's card came as "29.008 N" (phys30, 2026-11-16): a physics
card (``WorkedLayout.law_heading``) with more than three significant figures is rounded to
three. Nothing else changes: a card is never given figures it does not have, never replaced
by the working's value, and a whole number, a maths, chemistry or money value is exact as it
is written (6185 students, 180.156 g/mol, $1234.56, 3 groups of 40 from 130), and a sum of
money in a physics answer too: an electricity bill of $12.34 (Gemini on #2489).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.services.school_rounding import round_figures

if TYPE_CHECKING:
    from app.modules.chat.worked_solution import Answer

FIGURES = 3
# A measured decimal: digits, a point and more digits. A whole number is no measurement.
_DECIMAL = re.compile(r"-?\d+\.\d+")
# A note that only names a precision: "to 2 s.f.", "3 d.p.", "to 3 significant figures".
_PRECISION_NOTE = re.compile(
    r"^\s*(?:to\s+)?\d+\s*(?:s\.?\s*f\.?|d\.?\s*p\.?|significant\s+figures?|decimal\s+places?)\s*$",
    re.IGNORECASE,
)


def _figures(text: str) -> int:
    """Significant figures as written: 3.20 has three, 0.31 two, 29.008 five."""
    digits = text.lstrip("-").replace(".", "").lstrip("0")
    return len(digits) or 1


def card_answer(answer: Answer) -> Answer:
    """A physics ``answer`` with at most three significant figures (the module's rule)."""
    from app.services.subjects.registry import MONEY

    shown = answer.value.strip()
    if not _DECIMAL.fullmatch(shown) or _figures(shown) <= FIGURES:
        return answer
    if MONEY.names_currency(answer.unit or ""):
        return answer  # a sum of money is exact to the cent: $12.34 is never $12.3
    mantissa, exponent = round_figures(shown, FIGURES)
    places = max(FIGURES - 1 - exponent, 0)
    value = f"{mantissa.scaleb(exponent):.{places}f}"
    note = "" if _PRECISION_NOTE.match(answer.note or "") else answer.note
    return answer.model_copy(update={"value": value, "note": note})
