"""A reply's description of a field picture, checked before anything is drawn.

The reply says what to draw in a ```draw block (``contract``): point charges in a row, each
with its sign and, when the question states them, its amount; or two oppositely charged
plates. Each block is checked whole: a key the vocabulary does not hold, a fourth charge,
an amount or a sign the question does not state (``stated``), or amounts of different
kinds, and the block draws nothing. A picture is never drawn from a description it only
partly understood: a charge "at" a place the row cannot put it would be drawn in the wrong
place.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.field_lines.stated import (
    Charge,
    described_charge,
    held_to,
    named_signs,
    stated_charges,
)

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
    charges = _charges(described.charges or [], texts, described.part)
    return None if charges is None else FieldPicture(part=described.part, charges=charges)


def _charges(
    charges: list[_Charge], texts: Sequence[str], part: str | None
) -> tuple[DescribedCharge, ...] | None:
    """The described charges, each held to a charge the question states with its unit and
    sign; with none stated, signs alone (no amount may be made up), as many of each as the
    question names in words: one positive charge is no picture of "two negative charges"."""
    signs: list[Literal[1, -1]] = [-1 if charge.sign != "+" else 1 for charge in charges]
    stated = stated_charges(texts)
    if not stated:
        if any(charge.amount is not None for charge in charges):
            return None
        if not _signs_named(signs, texts, part):
            return None
        return tuple(DescribedCharge(float(sign), None) for sign in signs)
    if any(charge.amount is None for charge in charges):
        return None  # the question sizes its charges: the picture says them
    described = [
        described_charge(sign, charge.amount or "")
        for sign, charge in zip(signs, charges, strict=True)
    ]
    held = held_to([c for c in described if c is not None], stated)
    if held is None or len(held) != len(charges) or len({c.kind for c in held}) != 1:
        return None  # an amount the question does not state, or "2q" beside "3 μC"
    sizes = [charge.size for charge in held]
    if min(sizes) <= 0 or max(sizes) / min(sizes) > _MOST_RATIO:
        return None
    top = max(sizes)
    return tuple(
        DescribedCharge(charge.sign * charge.size / top, _label(charge)) for charge in held
    )


def _label(charge: Charge) -> str:
    return ("+" if charge.sign > 0 else "\u2212") + charge.written


def _signs_named(signs: list[Literal[1, -1]], texts: Sequence[str], part: str | None) -> bool:
    """The described signs are the ones the question names: all of them in its part (or a
    question of one picture), or among all its parts' together. A question that names no
    sign in words leaves the signs to the description."""
    named = named_signs(texts, part)
    if named is None:
        return True
    words, whole = named
    if whole:
        return sorted(signs) == sorted(words)
    left = list(words)
    for sign in signs:
        if sign not in left:
            return False
        left.remove(sign)
    return True
