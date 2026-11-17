"""A reply's description of a physics scene, checked whole before it is drawn.

The reply names the scene and the question's values it uses, never a coordinate:
{"kind": "scene", "scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°",
"height": "45 m"}}. Each value must be one the question states, with its unit and of the
part's kind, each used once (``values``); a speed belongs to the body whose mass it is
written beside. A part the scene does not take, a value the question does not state, or
a claim the scene does not know draws nothing: the scene is never drawn from a description
it only partly understood.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.scene_drawing.kinds import SCENES, SceneKind
from app.modules.physics.scene_drawing.values import Stated, nearer, stated_texts
from app.modules.physics.schemas import SimulationBlockSpec
from app.services.law_binding.givens import Given


class _Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    scene: str
    values: dict[str, str] = Field(default_factory=dict, max_length=6)
    sticks: bool | None = None
    elastic: bool | None = None
    harmonic: int | None = Field(default=None, ge=1, le=6)


def described_scene(body: str, texts: Sequence[str]) -> list[SimulationBlockSpec]:
    """The scene one ```draw block describes, drawn by its solver's builder; none when the
    block is no scene or does not check against ``texts`` (the user's message first)."""
    try:
        described = _Scene.model_validate(json.loads(body))
    except (ValueError, ValidationError):
        return []
    kind = SCENES.get(described.scene)
    if described.kind != "scene" or kind is None:
        return []
    stated = stated_texts(texts)
    values = _values(kind, described, stated)
    flags = _flags(kind, described, stated)
    if values is None or flags is None:
        return []
    return kind.draw({kind.parts[name].param: given for name, given in values.items()}, flags)


def _values(kind: SceneKind, described: _Scene, stated: Stated) -> dict[str, Given] | None:
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
    # Each body's speed is written beside its own mass, never the other body's.
    masses = [mass for mass, _speed in kind.bodies]
    for mass, speed in kind.bodies:
        others = [held[m] for m in masses if m != mass and m in held]
        if speed in held and mass in held and others:
            if not all(nearer(held[mass], other, held[speed]) for other in others):
                return None
    return held


def _flags(kind: SceneKind, described: _Scene, stated: Stated) -> dict[str, float] | None:
    """The claims a scene takes (the bodies stick, or bounce off elastically) as its
    solver's flags, exactly one when the scene takes any and none when it takes none; a
    standing wave's harmonic, when the question names it."""
    claimed = [name for name in ("sticks", "elastic") if getattr(described, name)]
    if len(claimed) != (1 if kind.claims else 0) or set(claimed) - set(kind.claims):
        return None
    flags = {kind.claims[name][0]: kind.claims[name][1] for name in claimed}
    if described.harmonic is not None:
        if described.scene != "standing_wave" or not stated.harmonic(described.harmonic):
            return None
        flags["harmonic"] = float(described.harmonic)
    return flags
