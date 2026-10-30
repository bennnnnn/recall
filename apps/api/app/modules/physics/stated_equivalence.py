"""An equivalence the question states, applied to its own amounts.

"An electric motor pumps 200 liter of water to a reservoir of height 6 m in 2 s …
Take 1 liter of water = 1 kg of water." (a grade 7 physics book, 2026-10-29): the
solver needs the water's mass, and the book says what a litre of it weighs. The amount
"200 liter of water" is read as "200 kg of water", and the sentence stating the
equivalence goes, so its 1 and 1 are not read as givens.
"""

from __future__ import annotations

import re

_UNIT = r"[A-Za-z]+"
_NUMBER = r"\d+(?:\.\d+)?"
# "Take 1 liter of water = 1 kg of water.", "1 L of water has a mass of 1 kg."
_STATED = re.compile(
    rf"(?:^|(?<=[.?!;])\s*|\s+)(?:take\s+|assume\s+(?:that\s+)?)?1\s*(?P<from>{_UNIT})\s+of\s+"
    rf"(?P<what>[a-z]+)\s+(?:=|is|equals|has\s+a\s+mass\s+of|weighs)\s*(?P<k>{_NUMBER})\s*"
    rf"(?P<to>{_UNIT})(?:\s+of\s+(?P=what))?\s*(?:[.;]|$)",
    re.IGNORECASE,
)


def _plural_of(unit: str) -> str:
    stem = unit.lower().removesuffix("s")
    return rf"{re.escape(stem)}s?"


def apply_stated_equivalence(text: str) -> str:
    """``text`` with its amounts of the thing in the stated unit, and that statement
    taken out; ``text`` unchanged when it states none, or the amount is not there."""
    stated = _STATED.search(text)
    if stated is None:
        return text
    rest = f"{text[: stated.start()]} {text[stated.end() :]}".strip()
    amount = re.compile(
        rf"(?<![\w.])(?P<n>{_NUMBER})\s*{_plural_of(stated.group('from'))}\s+of\s+"
        rf"(?={re.escape(stated.group('what'))}\b)",
        re.IGNORECASE,
    )
    factor = float(stated.group("k"))
    to = stated.group("to")
    rewritten, count = amount.subn(
        lambda match: f"{float(match.group('n')) * factor:g} {to} of ", rest
    )
    return rewritten if count else text
