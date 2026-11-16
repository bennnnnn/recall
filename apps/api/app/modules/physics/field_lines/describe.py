"""A reply's description of a field picture, checked before anything is drawn.

The reply says what to draw in a ```draw block (``contract``): point charges in a row, each
with its sign and, when the question states them, its amount; or two oppositely charged
plates. Each block is checked whole: a key the vocabulary does not hold, a fourth charge,
an amount the question does not state, or amounts of different kinds, and the block draws
nothing. A picture is never drawn from a description it only partly understood: a charge
"at" a place the row cannot put it would be drawn in the wrong place.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.givens import PHYSICS_UNITS, unit_dimension

_CHARGE_DIMENSION = "[current]^1 * [time]^1"
# "2q", "3 μC", "-1.5 nC": a number, then a multiple of q or a unit of charge.
_AMOUNT = re.compile(
    r"^\s*(?P<number>\d+(?:\.\d+)?|\.\d+)?\s*(?P<unit>[qQ]|[^\s\d][^\s]{0,11})\s*$"
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# The most one charge may be of another and still be drawn with a line count that says so.
_MOST_RATIO = 6.0


class _Charge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sign: Literal["+", "-", "\u2212"]
    amount: str | None = Field(default=None, max_length=16)


class _Plates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positive: Literal["top", "bottom"] = "top"


class _Description(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["field"]
    part: str | None = Field(default=None, pattern=r"^[a-h]$")
    charges: list[_Charge] | None = Field(default=None, min_length=1, max_length=3)
    plates: _Plates | None = None


@dataclass(frozen=True)
class DescribedCharge:
    # Signed, relative to the others.
    q: float
    # The question's amount, as written ("+2 μC", "-q"); None when it stated none.
    label: str | None


@dataclass(frozen=True)
class FieldPicture:
    """What one checked description draws."""

    part: str | None
    charges: tuple[DescribedCharge, ...] = ()
    # Which plate is positive, for a pair of plates.
    positive: Literal["top", "bottom"] | None = None


def read_description(body: str, texts: Sequence[str]) -> FieldPicture | None:
    """The picture one ```draw block describes, or None when it does not check."""
    try:
        data = json.loads(body)
        described = _Description.model_validate(data)
    except (ValueError, ValidationError):
        return None
    if (described.charges is None) == (described.plates is None):
        return None
    if described.plates is not None:
        return FieldPicture(part=described.part, positive=described.plates.positive)
    charges = _charges(described.charges or [], texts)
    return None if charges is None else FieldPicture(part=described.part, charges=charges)


def _charges(charges: list[_Charge], texts: Sequence[str]) -> tuple[DescribedCharge, ...] | None:
    amounts = [charge.amount for charge in charges]
    signs = [-1.0 if charge.sign != "+" else 1.0 for charge in charges]
    if all(amount is None for amount in amounts):
        return tuple(DescribedCharge(sign, None) for sign in signs)
    if any(amount is None for amount in amounts):
        return None
    read = [_amount(amount or "", texts) for amount in amounts]
    if any(item is None for item in read):
        return None
    kinds = {kind for kind, _size, _written in (item for item in read if item is not None)}
    if len(kinds) != 1:
        return None  # "2q" beside "3 μC": no one scale for both
    sizes = [size for _kind, size, _written in (item for item in read if item is not None)]
    if min(sizes) <= 0 or max(sizes) / min(sizes) > _MOST_RATIO:
        return None
    top = max(sizes)
    return tuple(
        DescribedCharge(sign * size / top, _label(sign, written))
        for sign, (_kind, size, written) in zip(
            signs, (item for item in read if item is not None), strict=True
        )
    )


def _amount(amount: str, texts: Sequence[str]) -> tuple[str, float, str] | None:
    """(kind, size, as written) of "2q" or "3 μC", when a message states its number."""
    match = _AMOUNT.match(amount)
    if match is None:
        return None
    number, unit = match.group("number"), match.group("unit")
    if number is None:
        if unit not in ("q", "Q"):
            return None  # "μC" alone states no amount
        number = "1"
    if not _stated(number, texts):
        return None
    if unit in ("q", "Q"):
        return "q", float(number), f"{_plain(number)}{unit}" if _plain(number) != "1" else unit
    expression = PHYSICS_UNITS.expression(unit)
    reading = unit_dimension(expression or "")
    if expression is None or reading is None or reading[0] != _CHARGE_DIMENSION:
        return None
    return "unit", float(number) * reading[1], f"{_plain(number)} {unit}"


def _stated(number: str, texts: Sequence[str]) -> bool:
    """A number a message states, as a number of its own: "2" of "2q" or "+2 μC"."""
    value = float(number)
    if value == 1:
        return True  # "q" alone: the unit the others are counted in
    return any(
        float(found.replace(",", ".")) == value for text in texts for found in _NUMBER.findall(text)
    )


def _plain(number: str) -> str:
    value = float(number)
    return f"{value:g}"


def _label(sign: float, written: str) -> str:
    return ("+" if sign > 0 else "\u2212") + written
