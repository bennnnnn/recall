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

from app.services.school_rounding import MOST_DIGITS, format_places, round_figures

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


def card_answer(answer: Answer, asked: tuple[int, int] = (0, -1)) -> Answer:
    """A physics ``answer`` with at most three significant figures (the module's rule), or
    to the precision the question asks (``asked``: significant figures, decimal places, as
    ``school_rounding.asked_rounding`` reads them; 0 and -1 for none): "to 4 s.f." keeps
    12.35, and its note says so (Claude on #2489)."""
    from app.services.subjects.registry import MONEY

    shown = answer.value.strip()
    if not _DECIMAL.fullmatch(shown) or MONEY.names_currency(answer.unit or ""):
        return answer  # a sum of money is exact to the cent: $12.34 is never $12.3
    figures, places = asked
    if figures > MOST_DIGITS or places > MOST_DIGITS:
        return answer  # "to 30 d.p.": no precision a card keeps, the value as written
    if places >= 0:
        written = len(shown.partition(".")[2])
        if written <= places:
            return answer
        return answer.model_copy(update={"value": format_places(shown, places)})
    keep = figures if figures > 0 else FIGURES
    if _figures(shown) <= keep:
        return answer
    mantissa, exponent = round_figures(shown, keep)
    value = f"{mantissa.scaleb(exponent):.{max(keep - 1 - exponent, 0)}f}"
    if figures > 0:
        return answer.model_copy(update={"value": value})
    note = "" if _PRECISION_NOTE.match(answer.note or "") else answer.note
    return answer.model_copy(update={"value": value, "note": note})
