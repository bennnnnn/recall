"""An equation to solve, stated in notation, whatever language its words are in.

The readers that keep a school question from being searched read English words, so the same
equation asked in another language was offered a web search: "x² + 5x + 6 = 0 को हल करें"
came back with quadratic-solver pages under it (2026-11-06). An equation reads the same in
every language. Only an equation is read here: quantities with units also appear in weather,
product, recipe and record questions that do need a search ("Wetter Berlin morgen 15 °C 20
km/h Wind?"), so they stay with the word readers. Pure, no IO.
"""

from __future__ import annotations

import re

from app.modules.turn_reading.coding import has_code_syntax
from app.modules.turn_reading.question_kinds import anyones

# One side of an equation in a variable: "2x^2 - 7x", "log2(x)", "sin(2x)", "x - 9".
_VARIABLE_TERM = re.compile(r"\d\s*[a-zA-Z(]|[a-zA-Z)]\s*(?:\^|\*\*|[²³])|\b[a-z]\s*[-+*/]\s*\d")
_EQUALS = re.compile(r"(?<![=<>!:])=(?!=)")
# Powers do not make a number to work with: "E = mc²" names a law, it states no sum.
_POWER = re.compile(r"(?:\^|\*\*)\s*\(?-?\d+\)?|[²³⁰¹⁴-⁹]")
# A link or markup holds "=" too: "?si=9xYz", "width=3px".
_LINK_OR_MARKUP = re.compile(r"://|www\.|<[a-z][^>]*>", re.IGNORECASE)
_SPAN = 40


def states_an_equation(text: str) -> bool:
    """An equation in a variable with a number in it: worked from the message, never
    something to search for."""
    if _LINK_OR_MARKUP.search(text) or has_code_syntax(text) or anyones(text):
        return False
    for match in _EQUALS.finditer(text):
        left = text[max(0, match.start() - _SPAN) : match.start()]
        right = text[match.end() : match.end() + _SPAN]
        if not (_VARIABLE_TERM.search(left) or _VARIABLE_TERM.search(right)):
            continue
        if re.search(r"\d", _POWER.sub(" ", left + " " + right)):
            return True
    return False
