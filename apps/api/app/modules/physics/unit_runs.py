"""A unit as a question writes it whole: "metres per second", "kN/m", "N kg^-1".

Read by the shared table factor by factor (``givens``), below every reader that needs it:
the extractors' givens (``extractors.written_unit``) and the asked unit (``ask``).
"""

from __future__ import annotations

import re

from app.modules.physics.givens import unit_at, unit_dimension, unit_readings, unit_symbol

# A unit written as a product of powers, factor by factor: the next one follows "/", "·",
# "*" or "per", a "." between letters ("m.s^-2"), or a space when it carries a power
# ("N kg^-1"). A plain word after a space is prose: "k = 200 and m = 2 kg".
_LETTERS = r"[A-Za-zµμΩÅ°]+"
_POWERS = r"\^-?\d+|-\d+|\d+|⁻?[¹²³]"
_POWER = re.compile(_POWERS)
_FIRST_FACTOR = re.compile(rf"(?P<space>[ \t]?){_LETTERS}(?P<power>{_POWERS})?")
_NEXT_FACTOR = re.compile(
    rf"(?:[ \t]*[/·*][ \t]*|\.(?=[A-Za-zµμ])|[ \t]+per[ \t]+|[ \t](?={_LETTERS}(?:{_POWERS})))"
    rf"{_LETTERS}(?:{_POWERS})?"
)


def unit_run(text: str, at: int, table: tuple[str, str] | None) -> str | None:
    """The whole unit written from ``at``: the table's reading and every factor after it.

    None when nothing unit-like is written: a word after a space with no power or factor.
    """
    if table is not None:
        start = text.find(table[0], at)
        at = start + len(table[0])
        power = _POWER.match(text, at)
        at, shaped = (power.end() if power else at), True
    else:
        first = _FIRST_FACTOR.match(text, at)
        if first is None:
            return None
        start, at = first.start() + len(first.group("space")), first.end()
        shaped = not first.group("space") or first.group("power") is not None
    while (factor := _NEXT_FACTOR.match(text, at)) is not None:
        at, shaped = factor.end(), True
    return text[start:at] if shaped else None


# Where one factor of a unit written in words ends and the next divides it: "metres per
# second", "km/h".
_DIVIDES = re.compile(r"[ \t]*(?:/|\bper\b)[ \t]*", re.IGNORECASE)


def _factor_symbol(factor: str) -> str | None:
    read = unit_at(factor, 0)
    if read is None or len(read[0]) != len(factor.strip()):
        return None
    return unit_symbol(read[1]) or (read[0] if read[0] == read[0].strip() else None)


def whole_unit(text: str, end: int) -> tuple[str, str] | None:
    """The unit written right after ``end``, whole: (as written, the spelling to show it in).

    "in metres per second" is m/s, not metres (``unit_at`` reads its first word only):
    asked so, a walk of 3000 feet in 10 minutes was carded 300 ft/min, verified (textbook
    round, 2026-11-26). A unit of one factor is shown as the table read it.
    """
    table = unit_at(text, end)
    if table is None:
        return None
    run = unit_run(text, end, table)
    factors = _DIVIDES.split(run) if run is not None else []
    symbols = [symbol for factor in factors if (symbol := _factor_symbol(factor)) is not None]
    if run is None or run == table[0] or len(factors) < 2 or len(symbols) != len(factors):
        return table[0], table[0]
    shown = "/".join(symbols)
    if _dimension(shown) is None or _dimension(shown) != _dimension(run):
        return table[0], table[0]
    return run, shown


def _dimension(unit: str) -> tuple[str, float, float] | None:
    return unit_dimension(unit_readings(unit)[-1])
