"""The charges a question states, and a described amount held to one of them.

A field picture's amounts are the question's: "+3 nC and +2 nC" is drawn with two positive
charges sized 3 to 2, never a + and a - (review of feat/field-lines), and "4 nC" is no
charge of a question that says "4 cm". Each charge is read with its unit and its sign, a
charge in units of the physics table ("3 nC", "-2 μC") or a multiple of q ("+2q", "-q"); a
charge written with no sign is positive, as a question means it.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.modules.physics.givens import PHYSICS_UNITS, unit_dimension
from app.services.law_binding.fit import read_givens

_CHARGE_DIMENSION = "[current]^1 * [time]^1"
_MINUS = frozenset({"-", "\u2212"})
# "+2q", "-q", "2q", "q": a multiple of q, never the q of "q1" or "quark". Each optional part
# is at most one character apart, so the scan stays linear.
_IN_Q = re.compile(r"(?<![\w.])([+\-\u2212])?(?:[ \t]?(\d+(?:\.\d+)?))?[ \t]?q(?!\w)")
# A described amount: its sign, its number and its unit, each optional but the unit.
_AMOUNT = re.compile(r"([+\-\u2212])?[ \t]?(\d+(?:\.\d+)?|\.\d+)?[ \t]?(\S{1,12})")

Kind = Literal["q", "unit"]


@dataclass(frozen=True)
class Charge:
    kind: Kind
    # Its size: a multiple of q, or coulombs.
    size: float
    sign: Literal[1, -1]
    # As the question writes it, without its sign: "2q", "q", "3 nC".
    written: str


def stated_charges(texts: Sequence[str]) -> list[Charge]:
    """The charges the first message that states any states, the user's last message first:
    a picture's amounts are that question's, never a number from another message."""
    for text in texts:
        found = _in_units(text) + _in_q(text)
        if found:
            return found
    return []


def _in_units(text: str) -> list[Charge]:
    charges = []
    for given in read_givens(text, PHYSICS_UNITS):
        if given.dimension != _CHARGE_DIMENSION or given.si is None:
            continue
        sign: Literal[1, -1] = -1 if text[: given.start].rstrip()[-1:] in _MINUS else 1
        charges.append(Charge("unit", abs(given.si), sign, f"{given.value:g} {given.unit}"))
    return charges


def _in_q(text: str) -> list[Charge]:
    charges = []
    for match in _IN_Q.finditer(text):
        size = float(match.group(2) or 1)
        written = "q" if size == 1 else f"{size:g}q"
        charges.append(Charge("q", size, -1 if match.group(1) in _MINUS else 1, written))
    return charges


def described_charge(sign: Literal[1, -1], amount: str) -> Charge | None:
    """A described charge's amount, read as a stated one is: "+2q", "-q", "3 μC". Its own
    sign, when it writes one, must be the charge's."""
    match = _AMOUNT.fullmatch(amount.strip())
    if match is None:
        return None
    written_sign, number, unit = match.groups()
    if written_sign is not None and (-1 if written_sign in _MINUS else 1) != sign:
        return None
    if unit in ("q", "Q"):
        size = float(number or 1)
        return Charge("q", size, sign, "q" if size == 1 else f"{size:g}q")
    expression = PHYSICS_UNITS.expression(unit)
    reading = unit_dimension(expression or "")
    if number is None or reading is None or reading[0] != _CHARGE_DIMENSION:
        return None
    return Charge("unit", float(number) * reading[1], sign, f"{float(number):g} {unit}")


def held_to(described: Sequence[Charge], stated: Sequence[Charge]) -> list[Charge] | None:
    """Each described charge matched to its own stated one, same kind, size and sign, in
    the question's own writing; None when any is not the question's."""
    left = list(stated)
    held = []
    for charge in described:
        match = next(
            (
                one
                for one in left
                if one.kind == charge.kind
                and one.sign == charge.sign
                and math.isclose(one.size, charge.size, rel_tol=1e-9)
            ),
            None,
        )
        if match is None:
            return None
        left.remove(match)
        held.append(match)
    return held
