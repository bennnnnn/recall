"""Asks for a pure number: a count of things, or an atom's level.

"How many turns does it have?" asks a count as "how long" asks a time; "to which level does
it fall?" asks a quantum number. Read as asking nothing, the first was answered with the
force on a wire and the second with the photon's energy (review 2026-11-12).
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.modules.physics.givens import PHYSICS_UNITS, unit_at, unit_dimension

# An atom's level, orbit or shell, asked as its quantum number.
STATE_ASK = re.compile(
    r"\b(?:which|what)\s+(?:energy\s+)?(?:levels?|orbits?|shells?)\b", re.IGNORECASE
)
# A count of things. A unit after it ("how many kWh") is the unit asked in
# (``ask.asked_unit``), unless it counts things itself (turns), and a count each second is a
# rate ("how many photons per second").
_COUNT_ASK = re.compile(r"\bhow\s+many\s+(?=[a-z])", re.IGNORECASE)
_RATE = re.compile(
    r"\bper\b|/|\b(?:each|every|a)\s+(?:second|minute|hour|day|year)\b", re.IGNORECASE
)
# The asked phrase of a count or a quantum number (``ask._dimension`` reads it).
PURE_NUMBER = "how many"
_NO_DIMENSION = "dimensionless"
_WORD = re.compile(r"[^\W\d_]+")


@lru_cache(maxsize=1)
def _caseless_symbols() -> dict[str, str]:
    return {spelling.lower(): expression for spelling, expression in PHYSICS_UNITS.symbols.items()}


def _unit_named(clause: str, at: int) -> str | None:
    """The unit written at ``at``, its symbol in any case: "how many kwh" asks in kWh."""
    unit = unit_at(clause, at)
    if unit is not None:
        return unit[1]
    word = _WORD.match(clause, at)
    return None if word is None else _caseless_symbols().get(word.group().lower())


def last_state_ask(text: str) -> re.Match[str] | None:
    """The question's last ask for an atom's level, orbit or shell."""
    found = list(STATE_ASK.finditer(text))
    return found[-1] if found else None


def pure_number_ask(clause: str) -> re.Match[str] | None:
    """Where the clause asks a pure number: a level ("which orbit") or a count of things
    ("how many turns"), not a count in a unit nor one each second."""
    state = STATE_ASK.match(clause, len(clause) - len(clause.lstrip()))
    if state is not None:
        return state
    count = _COUNT_ASK.search(clause)
    if count is None or _RATE.search(clause, count.end()):
        return None
    unit = _unit_named(clause, count.end())
    reading = None if unit is None else unit_dimension(unit)
    if unit is not None and (reading is None or reading[0] != _NO_DIMENSION):
        return None
    return count
