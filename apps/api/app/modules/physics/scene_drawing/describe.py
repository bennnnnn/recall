"""A reply's description of a physics scene, checked whole before it is drawn.

The reply names the scene and the question's values it uses, never a coordinate:
{"kind": "scene", "scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°",
"height": "45 m"}}. Each value must be one the question states, with its unit and of the
part's kind, each used once, and every other quantity the question states one the scene
can leave aside (``values``). The setup is then the physics readers' own: the question is
read as its solve reads it (``setup``), and the scene is drawn only from a reading of its
kind that agrees with every described value and claim, from the reader's values (a launch's
height and direction, a collision's type, the media's order, the planet). ``guards``
refuses what the words say the scene cannot carry. When the server cannot confirm the
setup, it draws nothing: a refusal is always safe, a wrong picture never is.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.scene_drawing.guards import GUARDS
from app.modules.physics.scene_drawing.kinds import SCENES, Quantities, SceneKind
from app.modules.physics.scene_drawing.setup import setup_readings
from app.modules.physics.scene_drawing.values import Stated, stated_texts
from app.modules.physics.schemas import PhysicsIntent, SimulationBlockSpec
from app.modules.physics.solvers.si import to_si
from app.services.law_binding.givens import Given

logger = logging.getLogger(__name__)


class _Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    scene: str
    values: dict[str, str] = Field(default_factory=dict, max_length=6)
    sticks: bool | None = None
    elastic: bool | None = None
    horizontal: bool | None = None


def described_scene(body: str, texts: Sequence[str]) -> list[SimulationBlockSpec]:
    """The scene one ```draw block describes, drawn by its solver's builder; none when the
    block is no scene or does not check against ``texts`` (the problem first)."""
    try:
        data = json.loads(body)
    except ValueError:
        logger.info("described scene not read: no JSON")
        return []
    if not isinstance(data, dict) or data.get("kind") != "scene":
        return []  # a field picture's block, or another kind
    try:
        described = _Scene.model_validate(data)
    except ValidationError as exc:
        logger.info("described scene not read: %s", exc.errors()[0].get("loc"))
        return []
    kind = SCENES.get(described.scene)
    if kind is None:
        logger.info("described scene %s not drawn: no such scene", described.scene[:40])
        return []
    stated = stated_texts(texts)
    held = _values(kind, described, stated)
    if held is None:
        logger.info(
            "described scene %s not drawn: its values (parts %s)",
            described.scene,
            ",".join(sorted(described.values)),
        )
        return []
    drawn = None
    if not GUARDS[described.scene](stated, held):
        readings = [r for r in setup_readings(texts[0]) if r.physics_op in kind.reads]
        drawn = next(
            (q for r in readings if (q := _agreed(kind, described, held, r)) is not None), None
        )
    if drawn is None:
        logger.info("described scene %s not drawn: no reading agrees", described.scene)
        return []
    return kind.draw(drawn)


def _values(kind: SceneKind, described: _Scene, stated: Stated) -> dict[str, Given] | None:
    """Each described value stated once, of its part's kind; every other stated quantity
    one the scene may leave aside."""
    if set(described.values) - set(kind.parts):
        return None
    if any(part.required and name not in described.values for name, part in kind.parts.items()):
        return None
    held: dict[str, Given] = {}
    for name, written in described.values.items():
        given = stated.take(written, kind.parts[name].sample)
        if given is None:
            return None
        held[name] = given
    if described.scene == "refraction" and "index_from" not in held:
        stated.take_air()  # "from air (n = 1.00)": the index a refraction from air needs not
    if "g" in kind.parts and "g" not in held:
        gravity = stated.take_gravity()  # "Take g = 9.8 m/s²": the reader must read it too
        if gravity is not None:
            held["g"] = gravity
    return None if stated.leaves_out(kind.tolerates) else held


def _same(given: Given, value: float, unit: str, param: str) -> bool:
    try:
        read = to_si(value, unit, expected_key=param)
    except Exception:
        return False
    written = given.si if given.si is not None else given.value
    return math.isclose(written, read, rel_tol=1e-6, abs_tol=1e-12)


def _agreed(
    kind: SceneKind, described: _Scene, held: dict[str, Given], reading: PhysicsIntent
) -> Quantities | None:
    """The reader's values to draw from, when its reading agrees with every described
    value and claim; None when it does not."""
    params = reading.physics_params or {}
    units = reading.physics_units or {}
    for name, given in held.items():
        param = kind.parts[name].param
        if not param or name in kind.unordered:
            continue
        if param not in params or not _same(given, params[param], units.get(param, ""), param):
            return None
    if kind.unordered:
        written = [held[name] for name in kind.unordered if name in held]
        read = [kind.parts[name].param for name in kind.unordered]
        if not _same_bodies(written, [(params.get(p), units.get(p, ""), p) for p in read]):
            return None
    if not _claims_agree(described, held, params, units):
        return None
    return {param: (params[param], units.get(param, "")) for param in kind.setup if param in params}


def _same_bodies(written: list[Given], read: list[tuple[float | None, str, str]]) -> bool:
    """The described masses are the reader's, in either order."""
    if len(written) != len(read) or any(value is None for value, _unit, _param in read):
        return False
    left = list(read)
    for given in written:
        match = next(
            (one for one in left if one[0] is not None and _same(given, one[0], one[1], one[2])),
            None,
        )
        if match is None:
            return False
        left.remove(match)
    return True


def _claims_agree(
    described: _Scene, held: dict[str, Given], params: dict[str, float], units: dict[str, str]
) -> bool:
    """A claim the reply makes is the reader's reading: the bodies stick or bounce off
    elastically as the reader read the collision; a launch is horizontal only when the
    reader read 0°; a block slides down a slope too steep for its friction to hold it."""
    scene = described.scene
    if scene == "collision":
        if bool(described.sticks) == bool(described.elastic):
            return False
        return params.get("elastic") == (1.0 if described.elastic else 0.0)
    if described.sticks or described.elastic:
        return False
    if scene == "projectile":
        if described.horizontal:
            return "angle" not in held and params.get("angle") == 0.0
        return "angle" in held
    if described.horizontal:
        return False
    if scene == "incline":
        angle, mu = params.get("angle"), params.get("mu")
        if params.get("motion_sign", 1.0) != 1.0 or angle is None or mu is None:
            return False
        return mu < math.tan(to_si(angle, units.get("angle", "deg"), expected_key="angle"))
    return True
