"""The unit written after a number, read from one subject's closed table of spellings.

A table, not free-form Pint parsing: Pint reads prose as units ("at" is a technical
atmosphere, "in" an inch, "a" a year). Each subject lists the spellings it reads and the
Pint expression of each; the dimension of an expression comes from Pint.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from functools import lru_cache

# The dimension of an angle. Pint calls degrees dimensionless, which would let
# a 30° angle compete with a friction coefficient.
ANGLE = "[angle]"

_ANGLE_UNITS = frozenset({"degree", "radian"})

# A unit ends where the next character cannot continue it: "m" is not "mass",
# "s" is not "s.f.", and "m/s" is not the "m" of "m/s".
_END = r"(?![A-Za-z0-9/^²³µμΩ°]|\.[A-Za-z])"

# A unit a table cannot list, read at a position: (spelling, Pint expression) or None.
SpecialUnit = Callable[[str, int], tuple[str, str] | None]


@lru_cache(maxsize=256)
def unit_dimension(expression: str) -> tuple[str, float, float] | None:
    """(dimension, scale, offset) of one Pint expression, angles kept apart."""
    from app.services.units import get_unit_registry

    if expression in _ANGLE_UNITS:
        scale = 1.0 if expression == "radian" else 0.017453292519943295
        return ANGLE, scale, 0.0
    registry = get_unit_registry()
    try:
        if expression == "degC":
            return _canonical({"[temperature]": 1}), 1.0, 273.15
        quantity = registry.Quantity(1.0, expression).to_base_units()
    except Exception:
        return None
    dimensionality = quantity.dimensionality
    powers = {str(name): float(dimensionality[name]) for name in dimensionality}
    return _canonical(powers), float(quantity.magnitude), 0.0


def _canonical(powers: dict[str, float]) -> str:
    """One spelling per dimension; Pint's own order depends on how it was built."""
    if not powers:
        return "dimensionless"
    return " * ".join(f"{name}^{power:g}" for name, power in sorted(powers.items()))


@lru_cache(maxsize=256)
def dimension_of(expression: str) -> str | None:
    """The canonical dimension of a Pint expression, or None when Pint cannot read it."""
    if not expression:
        return None
    reading = unit_dimension(expression)
    return None if reading is None else reading[0]


def _alternation(spellings: list[str]) -> str:
    """The spellings longest first; an empty table matches nothing, not an empty unit."""
    if not spellings:
        return "(?!)"
    return "|".join(re.escape(spelling) for spelling in sorted(spellings, key=len, reverse=True))


class UnitTable:
    """The unit spellings one subject reads, each mapped to a Pint expression.

    ``symbols`` are case-sensitive (a lowercase "a" is an article, "v" a variable);
    ``words`` are keyed in lowercase and matched without case. ``special`` reads a unit
    no table can list, such as physics' "0.8c"; ``exact`` names a spelling's expression
    when only ``special`` produces it.
    """

    def __init__(
        self,
        symbols: Mapping[str, str],
        words: Mapping[str, str],
        *,
        special: SpecialUnit | None = None,
        exact: Mapping[str, str] | None = None,
    ) -> None:
        self.symbols = dict(symbols)
        self.words = dict(words)
        self._special = special
        self._exact = dict(exact or {})
        self._symbol_re = re.compile(rf"[ \t]?(?P<unit>{_alternation(list(self.symbols))}){_END}")
        self._word_re = re.compile(
            rf"[ \t]?(?P<unit>{_alternation(list(self.words))}){_END}", re.IGNORECASE
        )

    def expression(self, spelling: str) -> str | None:
        """The Pint expression of one spelling from the table."""
        exact = self._exact.get(spelling)
        if exact is not None:
            return exact
        return self.symbols.get(spelling) or self.words.get(spelling.lower())

    def at(self, text: str, end: int) -> tuple[str, str] | None:
        """The unit written right after a number: (spelling, Pint expression)."""
        if self._special is not None:
            special = self._special(text, end)
            if special is not None:
                return special
        word = self._word_re.match(text, end)
        symbol = self._symbol_re.match(text, end)
        # The longer spelling wins: "m/s" over "m", "kg" over "g", "ms" over "m".
        if word is not None and (symbol is None or word.end() >= symbol.end()):
            spelling = word.group("unit")
            return spelling, self.words[spelling.lower()]
        if symbol is not None:
            spelling = symbol.group("unit")
            return spelling, self.symbols[spelling]
        return None
