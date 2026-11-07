"""The unit written after a stated number, read whole by the shared table."""

from __future__ import annotations

import re

from app.modules.physics.givens import unit_at

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


def _unit_run(text: str, at: int, table: tuple[str, str] | None) -> str | None:
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


def _reads_as(spelling: str, key: str) -> bool:
    from app.modules.physics.solvers.si import to_si
    from app.services.solving import SolveServiceError

    try:
        to_si(1.0, spelling, expected_key=key)
    except SolveServiceError:
        return False
    return True


def written_unit(text: str, end: int, key: str | None = None) -> str:
    """The unit written right after the number ending at ``end``; "" when none is.

    The whole unit, as the shared table reads it, so an extractor reads a prefix as the
    givens scan does: "k = 2 kN/m" was 2 N/m, "k = 500 g/s" 500 kg/s (audit 2026-11-07).
    For a slot ``key`` names, the reading of its dimension: the whole unit or the
    table's first part of it. "g = 10 N kg^-1" was read as newtons, and "ms^-2" in a g is
    m·s⁻², not a millisecond (review 2026-11-07). One nothing reads is kept as written,
    for ``to_si`` to refuse; it is never taken for the SI unit.
    """
    table = unit_at(text, end)
    run = _unit_run(text, end, table)
    if key is None or run is None:
        return table[0] if table else run or ""
    for spelling in dict.fromkeys(filter(None, (run, table and table[0]))):
        if _reads_as(spelling, key):
            return spelling
    return run
