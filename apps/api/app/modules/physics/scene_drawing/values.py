"""The values a question states, and a described value held to one of them.

A scene a reply describes is drawn from the question's own numbers: each value it names,
with its unit, must be one the question states, of the kind the scene's part takes (a
speed for a launch speed, an angle for a slope), each used once. A value the question
does not state is never drawn: the model may name a quantity, never invent one.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.physics.givens import PHYSICS_UNITS
from app.services.latex_markup import without_markup
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given
from app.services.number_text import fold_scientific

# The words that say which harmonic, where a question writes no number.
_ORDINALS = {"fundamental": 1, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}


def _plain(text: str) -> str:
    """The text as the physics readers read it: markup off, "5.97 x 10^24" one number."""
    return fold_scientific(without_markup(text))


@dataclass
class Stated:
    """The values one question states, the ones a described scene has used taken out."""

    text: str
    left: list[Given]

    @classmethod
    def of(cls, text: str) -> Stated:
        plain = _plain(text)
        return cls(plain, list(read_givens(plain, PHYSICS_UNITS)))

    def take(self, written: str, sample: str) -> Given | None:
        """The stated value ``written`` names ("20 m/s", "0.25"), of the kind ``sample``'s
        unit is ("m/s"; "" for a pure number), taken so no other part uses it."""
        read = list(read_givens(_plain(written), PHYSICS_UNITS))
        if len(read) != 1:
            return None
        (value,) = read
        kind = _dimension(sample)
        if value.dimension != kind:
            return None
        for given in self.left:
            if given.dimension != kind:
                continue
            same = (
                math.isclose(given.value, value.value, rel_tol=1e-9)
                if kind is None
                else given.si is not None
                and value.si is not None
                and math.isclose(given.si, value.si, rel_tol=1e-9)
            )
            if same:
                self.left.remove(given)
                return given
        return None

    def harmonic(self, written: int) -> bool:
        """The question names this harmonic: its number, or its word ("third")."""
        lower = self.text.lower()
        if any(word in lower and n == written for word, n in _ORDINALS.items()):
            return True
        return any(g.dimension is None and g.value == written for g in self.left)


def _dimension(sample: str) -> str | None:
    if not sample:
        return None
    read = read_givens(f"1 {sample}", PHYSICS_UNITS)
    return read[0].dimension if read else None


def nearer(owner: Given, other: Given, value: Given) -> bool:
    """``value`` is written nearer ``owner`` than ``other`` in the question: a speed is the
    body's whose mass it is written beside ("a 1.5 kg puck moving at 4 m/s")."""
    return abs(value.start - owner.start) < abs(value.start - other.start)


def stated_texts(texts: Sequence[str]) -> Stated:
    """The question's values: the user's message, as a scene draws the turn's question."""
    return Stated.of(texts[0] if texts else "")
