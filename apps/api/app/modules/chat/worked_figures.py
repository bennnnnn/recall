"""How many figures a worked answer's card keeps: three, rounded once from the working.

The working ends on its value unrounded and the card rounds it once (the owner's rule,
2026-11-13). The model chose the card's figures itself, and chose differently turn by turn:
"3.2 N (to 2 s.f.)" under working that reached 3.24 N, 1.4% from the answer, and "29.008 N"
on the next question (phys30, 2026-11-16). A plain number on the card is now the working's
own final value, or the answer's when the working states none, to three significant figures.
A card that is no plain number, one whose working ends on another value, or a value written
with fewer figures than three that is already exact (4.8, 96) stays as it is.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from app.services.school_rounding import round_figures

if TYPE_CHECKING:
    from app.modules.chat.worked_solution import Answer, Part

FIGURES = 3
_PLAIN = re.compile(r"-?\d+(?:\.\d+)?")
# The number a line ends on: "T = 3.2439\,\mathrm{N}", "= 5.377 m/s".
_LAST_VALUE = re.compile(
    r"=\s*(-?\d+(?:\.\d+)?)\s*(?:\\[,;: ]\s*)?(?:\\(?:mathrm|text)\{[^{}]*\}|[A-Za-z°/²³·^{}\s]*)?$"
)
# A note that only names a precision: "to 2 s.f.", "3 d.p.", "to 3 significant figures".
_PRECISION_NOTE = re.compile(
    r"^\s*(?:to\s+)?\d+\s*(?:s\.?\s*f\.?|d\.?\s*p\.?|significant\s+figures?|decimal\s+places?)\s*$",
    re.IGNORECASE,
)


def _decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _figures(text: str) -> int:
    """Significant figures as written: 3.20 has three, 0.31 two, 96 two."""
    digits = text.lstrip("-").replace(".", "").lstrip("0")
    return len(digits) or 1


def _working_value(part: Part) -> str | None:
    """The value the part's last substitution line reaches, as written."""
    lines = [step.tex for step in part.working if step.kind == "substitution"]
    if not lines:
        return None
    found = _LAST_VALUE.search(lines[-1].strip())
    return found.group(1) if found else None


def _agrees(card: Decimal, card_text: str, working: Decimal) -> bool:
    """The card is the working's value at the card's own rounding."""
    places = len(card_text.split(".")[1]) if "." in card_text else 0
    return abs(card - working) <= Decimal(5).scaleb(-places - 1)


def _three_figures(source: str) -> str:
    if _figures(source) <= FIGURES:
        return source  # exact already: 4.8, 96, 3.24
    mantissa, exponent = round_figures(source, FIGURES)
    value = mantissa.scaleb(exponent)
    places = max(FIGURES - 1 - exponent, 0)
    return f"{value:.{places}f}"


def card_answer(answer: Answer, part: Part) -> Answer:
    """``answer`` with its value to three figures from the working's own (module rule)."""
    shown = answer.value.strip()
    if not _PLAIN.fullmatch(shown):
        return answer
    card = _decimal(shown)
    source = shown
    working_text = _working_value(part)
    if card is not None and working_text is not None:
        working = _decimal(working_text)
        if working is None or not _agrees(card, shown, working):
            return answer  # the working ends on another value: the card is the reply's own
        if _figures(working_text) > _figures(shown):
            source = working_text
    value = _three_figures(source)
    if value == shown:
        return answer
    note = "" if _PRECISION_NOTE.match(answer.note or "") else answer.note
    return answer.model_copy(update={"value": value, "note": note})
