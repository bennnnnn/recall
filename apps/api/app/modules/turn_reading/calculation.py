# ruff: noqa: RUF001, RUF003 - the times sign of "3 × 10⁸ m/s" is part of the notation read
"""A calculation stated in notation, whatever language its words are in.

The readers that keep a school question from being searched read English words, so the same
homework asked in another language was offered a web search: "x² + 5x + 6 = 0 को हल करें"
came back with quadratic-solver pages under it, and "Une voiture roule à 72 km/h et freine
jusqu'à l'arrêt en 4 s" waited five seconds for Quizlet before its answer (2026-11-06). The
notation reads the same in every language: an equation in a variable, or quantities written
with their unit symbols. Pure, no IO.
"""

from __future__ import annotations

import re

from app.modules.turn_reading.coding import has_code_syntax
from app.modules.turn_reading.question_kinds import anyones

# One side of an equation in a variable: "2x^2 - 7x + 3", "log2(x)", "sin(2x)". A digit
# beside a letter or a power, so "a = b" in a sentence or "x = 5" alone is not one.
_VARIABLE_TERM = re.compile(r"\d\s*[a-zA-Z(]|[a-zA-Z)]\s*(?:\^|\*\*|[²³])|\b[a-z]\s*[-+*/]\s*\d")
_EQUALS = re.compile(r"(?<![=<>!:])=(?!=)")

# A number with the symbol of an SI or school unit after it: "72 km/h", "9,81 m/s²",
# "4 s", "0.5 mol". Symbols, not words, so they read the same in every language.
_UNIT = (
    r"(?:k?m/s(?:²|\^2|2)?|km/h|mph|m/s|[kcmµμn]?m(?:²|³|\^[23])?|[kmµμ]?g|[kmµμ]?s|min|h"
    r"|[kMm]?N|[kM]?J|[kMm]?W|[kmµμ]?V|[mµμ]?A|[kMm]?Ω|ohms?|[kM]?Hz|m?mol|mL|L|M|K|°C|°F"
    r"|[kM]?Pa|atm|bar|C|F|T|eV|cal|kcal|kWh)"
)
# The times sign of "3 × 10⁸ m/s" may stand before the power.
_QUANTITY = re.compile(
    rf"(?<![\w.,])\d+(?:[.,]\d+)?(?:\s*[x×]\s*10\^?-?\d+)?\s*(?P<unit>{_UNIT})(?![\w/])"
)


def states_a_calculation(text: str) -> bool:
    """An equation to work in a variable, or quantities given in two units or more: a sum
    worked from what the message gives, never something to search for."""
    if has_code_syntax(text) or anyones(text):
        return False
    if _states_an_equation(text):
        return True
    # Quantities of more than one unit: a list of one unit ("Mon 5h, Tue 7h, Wed 6h of
    # sleep") is data to draw, not a sum to work.
    return len({_unit_of(quantity) for quantity in _QUANTITY.finditer(text)}) >= 2


def _states_an_equation(text: str) -> bool:
    for match in _EQUALS.finditer(text):
        left = text[max(0, match.start() - 40) : match.start()]
        right = text[match.end() : match.end() + 40]
        if _VARIABLE_TERM.search(left) or _VARIABLE_TERM.search(right):
            return True
    return False


def _unit_of(quantity: re.Match[str]) -> str:
    return quantity.group("unit")
