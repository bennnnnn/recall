"""An equivalence the question states, applied to its own amounts.

"An electric motor pumps 200 liter of water to a reservoir of height 6 m in 2 s …
Take 1 liter of water = 1 kg of water." (a grade 7 physics book, 2026-10-29): the
solver needs the water's mass, and the book says what a litre of it weighs. The amount
"200 liter of water" is read as "200 kg of water", and the sentence stating the
equivalence goes, so its 1 and 1 are not read as givens.
"""

from __future__ import annotations

import re

# A unit, with its power when it has one: "kg", "m3", "m^3", "m³".
_UNIT = r"[A-Za-z]+(?:\^?\d|[²³])?"
_NUMBER = r"\d+(?:\.\d+)?"
# An amount as written: "1,500", "200", ".5".
_AMOUNT = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
# "Take 1 liter of water = 1 kg of water.", "1 L of water has a mass of 1 kg.", and with
# what it is of unsaid: "(Note that 1 liter = 1 kg)" (Gemini on #2503: its 1 kg was the mass,
# 14.7 W for 4414.5 W). It may close a bracketed note, or a clause before the question.
_STATED = re.compile(
    rf"(?<![\w.,])(?:take\s+|assume\s+(?:that\s+)?)?1\s*(?P<from>{_UNIT})(?:\s+of\s+"
    rf"(?P<what>[a-z]+))?(?:\s*=|\s+(?:is|equals|has\s+a\s+mass\s+of|weighs))\s*"
    rf"(?P<k>{_NUMBER})\s*(?P<to>{_UNIT})(?:\s+of\s+(?P=what))?\s*(?:[.;),]|$)",
    re.IGNORECASE,
)


def _plural_of(unit: str) -> str:
    """Every spelling of the stated unit: "L", "liter" and "litres" are one unit."""
    if unit.lower() in _LITRES:
        return r"(?:l|lit(?:er|re)s?)\b"
    stem = unit.lower().removesuffix("s")
    return rf"{re.escape(stem)}s?"


def states_an_equivalence(text: str) -> bool:
    """Whether ``text`` states an equivalence: left after ``apply_stated_equivalence``, it
    was not applied, and its 1 and its 1 kg are no givens (``unread``)."""
    return _STATED.search(text) is not None


def apply_stated_equivalence(text: str) -> str:
    """``text`` with its amounts of the thing in the stated unit, and that statement
    taken out; ``text`` unchanged when it states none, or the amount is not there."""
    stated = _STATED.search(text)
    if stated is None:
        return text
    rest = f"{text[: stated.start()]} {text[stated.end() :]}".strip()
    what = stated.group("what")
    amount = _amount_of(stated.group("from"), what)
    factor = float(stated.group("k"))
    to = stated.group("to")
    if what is not None and _known_density(what, stated.group("from"), factor, to):
        # Water's own density, which the solver already uses: the statement adds nothing.
        return rest if amount.search(rest) else text
    rewritten, count = amount.subn(
        lambda match: (
            f"{float(match.group('n').replace(',', '')) * factor:.10g} {to}" + match.group("tail")
        ),
        rest,
    )
    return rewritten if count else text


def _amount_of(unit: str, what: str | None) -> re.Pattern[str]:
    """An amount in the stated unit: of the thing it states ("200 liter of water"), or any
    when it states none ("300 liters")."""
    tail = rf"\s+of\s+(?={re.escape(what)}\b)" if what is not None else r"(?![A-Za-z\d])"
    return re.compile(
        rf"(?<![\w.,])(?P<n>{_AMOUNT})\s*{_plural_of(unit)}(?P<tail>{tail})", re.IGNORECASE
    )


_LITRES = frozenset({"l", "liter", "liters", "litre", "litres"})


def _known_density(what: str, unit: str, factor: float, to: str) -> bool:
    """1 litre of water is 1 kg: what the solver takes water to weigh anyway."""
    return (
        what.lower() == "water"
        and unit.lower() in _LITRES
        and to.lower() in {"kg", "kilogram", "kilograms"}
        and factor == 1.0
    )
