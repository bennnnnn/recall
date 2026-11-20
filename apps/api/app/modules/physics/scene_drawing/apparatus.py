"""A circuit or a plane mirror a reply describes, checked against the question and drawn by
the builders physics' solves draw with.

"Draw the circuit diagram for this" after a worked series circuit came back as a Mermaid
flowchart, and "Construct a ray diagram ... in front of a plane mirror" as "I can't draw the
rays myself" (Grade 8 round, 2026-11-18): neither is a scene of the closed vocabulary, and a
question in parts never reached a solve that draws one. The reply names the setup in a
```draw block, never a coordinate:

- {"kind": "circuit", "arrangement": "series", "supply": "120 V", "resistors": ["40 Ω",
  "40 Ω"]}: every value one the question states, and the circuit the physics readers read
  in it (``setup_readings``: the whole question, then each of its parts) the same network.
  The schematic is the solve's own (``circuit_scenes``), labelled with the stated values
  and the current the server works out from them.
- {"kind": "plane_mirror", "object_distance": "30 cm"} (the distance only when the
  question states one): a question that names a plane mirror and no curved one. The
  server places the object, its virtual image as far behind the mirror, and two rays
  from the object's tip with their construction lines behind the mirror.

A description that does not check draws nothing: a refusal is always safe.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.display import GIVEN_FIGURES, plain_number
from app.modules.physics.givens import PHYSICS_UNITS
from app.modules.physics.numbers import normalize_physics_units
from app.modules.physics.scene_drawing.setup import setup_readings
from app.modules.physics.scene_drawing.values import Stated
from app.modules.physics.schemas import (
    OpticsArrow,
    OpticsRay,
    OpticsSpec,
    PhysicsIntent,
    SimulationBlockSpec,
)
from app.modules.physics.solver import solve_physics
from app.modules.physics.solvers.resistor_network import RESISTOR_KEY_RE
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given

logger = logging.getLogger(__name__)

# The texts a follow-up's picture may be of: the problem it points back to, the line, and
# the user's messages before it, newest first.
_MAX_TEXTS = 4
# The readings of a network, by its wiring; a current's reading carries the supply.
_READS: dict[str, tuple[str, ...]] = {
    "series": ("series_current", "series_resistance"),
    "parallel": ("parallel_current", "parallel_resistance"),
}
_PLANE_MIRROR = re.compile(r"\bplane\s+mirrors?\b", re.IGNORECASE)
_CURVED = re.compile(
    r"\b(?:concave|convex|curved|spherical|parabolic)\b|\bfocal\b|\blens(?:es)?\b",
    re.IGNORECASE,
)


class _Circuit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["circuit"]
    arrangement: Literal["series", "parallel"]
    resistors: list[str] = Field(min_length=2, max_length=6)
    supply: str | None = None


class _Mirror(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["plane_mirror"]
    object_distance: str | None = None


def described_apparatus(body: str, texts: Sequence[str]) -> list[SimulationBlockSpec]:
    """The circuit or plane mirror one ```draw block describes, of the first of ``texts``
    it checks against; none when it is neither or checks against none."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    kind = data.get("kind") if isinstance(data, dict) else None
    if kind not in ("circuit", "plane_mirror"):
        return []
    try:
        described: _Circuit | _Mirror = (
            _Circuit.model_validate(data) if kind == "circuit" else _Mirror.model_validate(data)
        )
    except ValidationError as exc:
        logger.info("described %s not read: %s", kind, exc.errors()[0].get("loc"))
        return []
    for text in [t for t in texts if t and t.strip()][:_MAX_TEXTS]:
        drawn = (
            _circuit(described, text)
            if isinstance(described, _Circuit)
            else _mirror(described, text)
        )
        if drawn:
            return drawn
    logger.info("described %s not drawn: no text it checks against", kind)
    return []


def _quantity(written: str, sample: str) -> Given | None:
    """``written`` as one quantity of ``sample``'s kind ("40 Ω" of "Ω"), else None."""
    read = list(read_givens(f"{written}", PHYSICS_UNITS))
    kind = read_givens(f"1 {sample}", PHYSICS_UNITS)
    if len(read) != 1 or not kind or read[0].dimension != kind[0].dimension:
        return None
    return read[0]


def _si(given: Given) -> float:
    return given.si if given.si is not None else given.value


def _stated(given: Given, stated: Stated) -> bool:
    """The question states this value, of this kind (a value named twice, "two 40 Ω
    resistors", is stated once)."""
    return any(
        one.dimension == given.dimension and math.isclose(_si(one), _si(given), rel_tol=1e-9)
        for one in stated.left
    )


def _circuit(described: _Circuit, text: str) -> list[SimulationBlockSpec]:
    stated = Stated.of(normalize_physics_units(text))
    resistors = [_quantity(value, "Ω") for value in described.resistors]
    supply = _quantity(described.supply, "V") if described.supply else None
    if any(r is None or not _stated(r, stated) for r in resistors):
        return []
    if described.supply and (supply is None or not _stated(supply, stated)):
        return []
    ohms = sorted(_si(r) for r in resistors if r is not None)
    readings = [
        r for r in setup_readings(stated.text) if r.physics_op in _READS[described.arrangement]
    ]
    # The current's reading first: it carries the supply, which the schematic labels.
    readings.sort(key=lambda r: _READS[described.arrangement].index(r.physics_op or ""))
    for reading in readings:
        if _same_network(reading, ohms, supply):
            return _drawn(reading)
    return []


def _same_network(reading: PhysicsIntent, ohms: list[float], supply: Given | None) -> bool:
    """The reader's network is the described one: its resistances, and its supply."""
    params = reading.physics_params or {}
    read = sorted(value for key, value in params.items() if RESISTOR_KEY_RE.fullmatch(key))
    if len(read) != len(ohms) or not all(
        math.isclose(a, b, rel_tol=1e-9) for a, b in zip(read, ohms, strict=True)
    ):
        return False
    if supply is None:
        return reading.physics_op is not None and reading.physics_op.endswith("_resistance")
    return "V" in params and math.isclose(params["V"], _si(supply), rel_tol=1e-9)


def _drawn(reading: PhysicsIntent) -> list[SimulationBlockSpec]:
    try:
        specs = solve_physics(reading).simulation_specs
    except Exception as exc:  # A circuit that cannot be solved is no picture.
        logger.info("described circuit not drawn (%s)", type(exc).__name__)
        return []
    return [spec for spec in specs if spec.type == "circuit"]


def _mirror(described: _Mirror, text: str) -> list[SimulationBlockSpec]:
    if not _PLANE_MIRROR.search(text) or _CURVED.search(text):
        return []
    distance = None
    if described.object_distance:
        distance = _quantity(described.object_distance, "m")
        if (
            distance is None
            or not _stated(distance, Stated.of(normalize_physics_units(text)))
            or distance.value <= 0
        ):
            return []
    return plane_mirror_image(distance)


def plane_mirror_image(distance: Given | None) -> list[SimulationBlockSpec]:
    """An object before a plane mirror and its virtual image as far behind it: two rays
    from the object's tip, each reflected at an equal angle and traced back, dashed, to the
    image's tip. With a stated distance, both are labelled with it."""
    d, h = (distance.value, 0.5 * distance.value) if distance is not None else (2.0, 1.0)
    unit = distance.unit if distance is not None else ""
    label = f"{plain_number(d, GIVEN_FIGURES)} {unit}".strip() if distance is not None else None
    rays = []
    for meets in (1.5 * h, 0.5 * h):
        # Reflected at the angle it met the mirror: back to x = -d at 2 * meets - h.
        rays.append(OpticsRay(points=[[-d, h], [0.0, meets], [-d, 2 * meets - h]]))
        rays.append(OpticsRay(points=[[0.0, meets], [d, h]], virtual=True))
    spec: dict[str, Any] = {
        "element": "plane_mirror",
        "object": OpticsArrow(x=-d, height=h, label=f"dₒ = {label}" if label else None),
        "image": OpticsArrow(x=d, height=h, label=f"dᵢ = {label}" if label else None, virtual=True),
        "rays": rays,
    }
    return [
        SimulationBlockSpec(
            type="rays",
            title="Ray Diagram",
            title_key="mirror",
            optics=OpticsSpec(**spec),
            x_min=-d * 1.4,
            x_max=d * 1.4,
            y_min=-h * 0.6,
            y_max=h * 2.4,
            alt=(
                "An object in front of a plane mirror and its image as far behind it: "
                "upright, the same size, and virtual."
            ),
        )
    ]
