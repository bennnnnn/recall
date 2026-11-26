"""An arrow the question writes by its components ("A [4 5] N", "velocity [5 2] m/s"), held to
the vector the question writes.

"Find if these concurrent forces are in equilibrium by drawing the forces head to tail. A [4
5] N, B [-3 -2] N and C [-2 -3] N" gives no size and no direction in words, so the arrows of a
```draw block could not be checked and nothing was drawn (textbook round, 2026-11-25). An
arrow may name its components instead: {"name": "A", "components": "[4 5]"}. They must be a
vector the question writes, number for number, each written vector serving one arrow, in the
unit written after it (of the picture's quantity, or none at all); its size and angle are
worked out here. A picture of written vectors draws every one of them of its kind.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.modules.physics.givens import PHYSICS_UNITS
from app.modules.physics.scene_drawing.values import dimension_of
from app.modules.physics.scene_drawing.vector_layout import Arrow
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given

_NUMBER = r"-?\d+(?:\.\d+)?"
# "[4 5]", "[ -3 -2]", "(4, 5)", "[4, -2]": two components in brackets.
_WRITTEN = re.compile(rf"[\[(]\s*({_NUMBER})\s*[,;]?\s+({_NUMBER})\s*[\])]|"
                      rf"[\[(]\s*({_NUMBER})\s*[,;]\s*({_NUMBER})\s*[\])]")  # fmt: skip
# The unit written after the bracket: "N", "m/s", "kg m/s", or none.
_UNIT = re.compile(r"[ \t]*([A-Za-zμ/²·][A-Za-zμ/²·^0-9 ]{0,10})")
_MINUS = str.maketrans({0x2212: "-", 0x2013: "-", 0x2014: "-"})


@dataclass(frozen=True)
class Written:
    """One vector the question writes: its components, its unit and where it is."""

    x: float
    y: float
    unit: str
    start: int
    end: int


def written_vectors(text: str) -> list[Written]:
    """Every two-component vector ``text`` writes, in order, with the unit after it."""
    plain = text.translate(_MINUS)
    found: list[Written] = []
    for match in _WRITTEN.finditer(plain):
        x, y = (g for g in match.groups() if g is not None)
        found.append(Written(float(x), float(y), _unit_after(plain, match.end()), *match.span()))
    return found


def _unit_after(text: str, at: int) -> str:
    """The unit written straight after a vector, as the physics readers read it, or ""."""
    match = _UNIT.match(text, at)
    if match is None:
        return ""
    words = match.group(1).split()
    for size in range(len(words), 0, -1):
        unit = " ".join(words[:size]).rstrip(".,;")
        read = read_givens(f"1 {unit}", PHYSICS_UNITS)
        if read and read[0].dimension is not None and read[0].unit == unit:
            return unit
    return ""


def _components(written: str) -> tuple[float, float] | None:
    match = _WRITTEN.search(written.translate(_MINUS))
    if match is None:
        return None
    x, y = (float(g) for g in match.groups() if g is not None)
    return x, y


def component_arrow(
    name: str | None,
    components: str,
    quantity_unit: str,
    question: str,
    used: set[int],
) -> Arrow | None:
    """The arrow of the written vector ``components`` names, not used yet (``used``: the
    starts of those drawn), in a unit of the picture's quantity or none; None when the
    question writes no such vector."""
    wanted = _components(components)
    if wanted is None or wanted == (0.0, 0.0):
        return None
    kind = dimension_of(quantity_unit)
    for vector in written_vectors(question):
        if vector.start in used or (vector.x, vector.y) != wanted:
            continue
        unit_kind = dimension_of(vector.unit) if vector.unit else None
        if vector.unit and unit_kind != kind:
            continue
        used.add(vector.start)
        size = math.hypot(vector.x, vector.y)
        si = _si(size, vector.unit)
        given = Given(vector.start, vector.end, size, vector.unit, unit_kind, si)
        label = f"[{vector.x:g}, {vector.y:g}]" + (f" {vector.unit}" if vector.unit else "")
        named = _named(name, question, vector.start)
        return Arrow(
            given=given,
            label=f"{named} = {label}"[:24] if named else label[:24],
            angle=math.degrees(math.atan2(vector.y, vector.x)) % 360.0,
            compass=False,
            name=None,
            mass=None,
            mass_label=None,
            direction="",
            key=" ".join((name or "").split()).lower(),
        )
    return None


def _si(size: float, unit: str) -> float:
    if not unit:
        return size
    read = read_givens(f"{size} {unit}", PHYSICS_UNITS)
    return read[0].si if read and read[0].si is not None else size


def _named(name: str | None, question: str, start: int) -> str | None:
    """The arrow's name when the question writes it just before its vector ("A [4 5] N",
    "a = [4 4]", "velocity of [5 2]" is no name)."""
    word = (name or "").strip()
    if not word or len(word) > 3:
        return None
    before = question.translate(_MINUS)[max(0, start - 8) : start]
    return word if re.search(rf"(?<!\w){re.escape(word)}\s*=?\s*$", before) else None


def left_out(question: str, used: set[int], quantity_unit: str) -> bool:
    """A vector the question writes of the picture's kind (or with no unit) that no arrow
    drew: a picture of written vectors draws each one."""
    kind = dimension_of(quantity_unit)
    return any(
        vector.start not in used and (not vector.unit or dimension_of(vector.unit) == kind)
        for vector in written_vectors(question)
    )
