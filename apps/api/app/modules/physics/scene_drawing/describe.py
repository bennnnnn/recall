"""A reply's description of a physics scene, checked whole before it is drawn.

The reply names the scene and the question's values it uses, never a coordinate:
{"kind": "scene", "scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°",
"height": "45 m"}}. Each value must be one the question states, with its unit and of the
part's kind, each used once; every other quantity the question states must be one the
scene can leave aside (``values``); a speed belongs to the mass in its own clause; and the
question's words must state nothing the scene cannot carry: a direction, an angle's
reference, another apparatus (``guards``). When the server cannot confirm the setup, it
draws nothing: a refusal is always safe, a wrong picture never is.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.scene_drawing.confirm import CONFIRMS
from app.modules.physics.scene_drawing.guards import GUARDS
from app.modules.physics.scene_drawing.kinds import SCENES, SceneKind
from app.modules.physics.scene_drawing.values import Stated, stated_texts
from app.modules.physics.schemas import SimulationBlockSpec
from app.services.law_binding.givens import Given

logger = logging.getLogger(__name__)

_HORIZONTALLY = re.compile(r"\bhorizontally\b", re.IGNORECASE)
_LENGTH_KIND = "[length]^1"


class _Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    scene: str
    values: dict[str, str] = Field(default_factory=dict, max_length=6)
    sticks: bool | None = None
    elastic: bool | None = None
    horizontal: bool | None = None
    harmonic: int | None = Field(default=None, ge=1, le=6)


def described_scene(body: str, texts: Sequence[str]) -> list[SimulationBlockSpec]:
    """The scene one ```draw block describes, drawn by its solver's builder; none when the
    block is no scene or does not check against ``texts`` (the user's message first)."""
    try:
        data = json.loads(body)
    except ValueError:
        logger.info("described scene not read: no JSON")
        return []
    if not isinstance(data, dict) or data.get("kind") != "scene":
        return []  # a field picture's block, or another kind
    # A harmonic is the scene's claim, wherever the reply put it.
    values = data.get("values")
    if isinstance(values, dict) and "harmonic" in values and "harmonic" not in data:
        written = values.pop("harmonic")
        data["harmonic"] = int(written) if str(written).isdigit() else written
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
    values = _values(kind, described, stated)
    flags = _flags(kind, described, stated)
    if values is None or flags is None:
        logger.info(
            "described scene %s not drawn: %s (parts %s)",
            described.scene,
            "its values" if values is None else "its claims",
            ",".join(sorted(described.values)),
        )
        return []
    # The words confirm the setup the scene draws, and say nothing it cannot carry.
    if not CONFIRMS[described.scene](stated, values, flags) or GUARDS[described.scene](
        stated, values
    ):
        logger.info("described scene %s not drawn: its setup unconfirmed", described.scene)
        return []
    drawn = {kind.parts[name].param: given for name, given in values.items()}
    return kind.draw({param: given for param, given in drawn.items() if param}, flags)


def _values(kind: SceneKind, described: _Scene, stated: Stated) -> dict[str, Given] | None:
    if set(described.values) - set(kind.parts):
        return None
    for name, part in kind.parts.items():
        needed = part.required or (name == "angle" and described.scene == "projectile")
        if needed and name not in described.values and not described.horizontal:
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
        gravity = stated.take_gravity()  # "Take g = 9.8 m/s²": the scene is drawn under it
        if gravity is not None:
            held["g"] = gravity
    # The scene is the question's whole setup: no stated quantity it cannot leave aside.
    if stated.leaves_out(kind.tolerates):
        return None
    return held


def _harmonic(stated: Stated, described: int | None) -> int | None:
    """The harmonic the question names ("third harmonic", "n = 3"), or the one its stated
    wavelength fits on the string (n = 2L/λ, a whole number); the description's own, when it
    gives one, must be that one."""
    named = stated.harmonics()
    if not named:
        length = next((g for g in stated.taken if g.dimension == _LENGTH_KIND), None)
        waves = stated.lengths_left()
        if length is None or len(waves) != 1 or not length.si or not waves[0].si:
            return None
        fits = 2 * length.si / waves[0].si
        if abs(fits - round(fits)) > 1e-6 or not 1 <= round(fits) <= 6:
            return None
        named = {round(fits)}
    if described is not None:
        return described if described in named else None
    return min(named) if len(named) == 1 else None


def _flags(kind: SceneKind, described: _Scene, stated: Stated) -> dict[str, float] | None:
    """The claims a scene takes, as its solver's flags: a collision's one claim (the bodies
    stick, or bounce off elastically), a projectile launched horizontally when the question
    says so, a standing wave's harmonic when the question names it ("third harmonic",
    "n = 3", "fundamental"); a claim the question does not support draws nothing."""
    claims = {"sticks": described.sticks, "elastic": described.elastic}
    claimed = [name for name, on in claims.items() if on]
    if len(claimed) != (1 if kind.claims else 0) or set(claimed) - set(kind.claims):
        return None
    flags = {kind.claims[name][0]: kind.claims[name][1] for name in claimed}
    if described.horizontal:
        if described.scene != "projectile" or "angle" in described.values:
            return None
        if _HORIZONTALLY.search(stated.text) is None:
            return None
        flags["angle"] = 0.0
    if described.scene == "standing_wave":
        harmonic = _harmonic(stated, described.harmonic)
        if harmonic is None:
            return None
        flags["harmonic"] = float(harmonic)
    elif described.harmonic is not None:
        return None
    return flags
