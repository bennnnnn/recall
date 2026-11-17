"""The scenes a reply may describe, each drawn by the builder its solver draws with.

Each kind names its parts (a launch speed, a slope's angle, two masses), the unit each is
in, and how it is drawn: through the kind's own solver, whose verified scene is the picture
(the projectile's arc, the incline's forces, the Atwood machine, the collision, the spring,
the pendulum, the orbit, the ray diagrams), or, where the solver needs a value the question
does not state, straight through the scene builder it draws with (a standing wave's loops
need only the string's length and the harmonic). There is no second builder: a kind not
listed is not drawn.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from app.modules.physics.schemas import PhysicsIntent, SimulationBlockSpec
from app.modules.physics.solver import solve_physics
from app.modules.physics.solvers.si import to_si
from app.modules.physics.solvers.wave_scenes import standing_scene
from app.services.law_binding.givens import Given

logger = logging.getLogger(__name__)

Scenes = list[SimulationBlockSpec]
Drawn = Callable[[Mapping[str, Given], Mapping[str, float]], Scenes]


@dataclass(frozen=True)
class Part:
    """One value a scene takes: the solver's parameter ("" for a value the scene is checked
    with but does not draw, a lens's object height), a unit of its kind ("" for a pure
    number), and whether the scene can do without it."""

    param: str
    sample: str
    required: bool = True
    # Every value the question states of this part's kind must be one the scene uses: an
    # unused one is another body or another situation (a pulley's own mass, a wall). A
    # label only (a block's mass on a slope) says nothing of the situation.
    whole: bool = True


@dataclass(frozen=True)
class SceneKind:
    parts: Mapping[str, Part]
    draw: Drawn
    # Claims only the model can make (the bodies stick together), each a solver flag.
    claims: Mapping[str, tuple[str, float]] = field(default_factory=dict)
    # Parts written by one body: each (mass, speed) pair's speed sits beside its mass.
    bodies: tuple[tuple[str, str], ...] = ()


def _solved(kind: str, op: str, fixed: Mapping[str, tuple[float, str]] | None = None) -> Drawn:
    """The scene the solver for ``op`` draws from these values, or none when it draws none
    (a value it cannot use, a situation it does not take)."""

    def draw(values: Mapping[str, Given], flags: Mapping[str, float]) -> Scenes:
        params = {name: given.value for name, given in values.items()}
        units = {name: given.unit for name, given in values.items()}
        for name, (value, unit) in (fixed or {}).items():
            params.setdefault(name, value)
            units.setdefault(name, unit)
        for name, value in flags.items():
            params[name], units[name] = value, ""
        try:
            intent = PhysicsIntent(
                kind=kind,  # type: ignore[arg-type]
                operation="solve",
                physics_op=op,
                physics_params=params,
                physics_units=units,
            )
            return list(solve_physics(intent).simulation_specs)
        except Exception as exc:  # A scene that cannot be drawn is no picture.
            logger.info("described scene not drawn op=%s (%s)", op, type(exc).__name__)
            return []

    return draw


def _banked(values: Mapping[str, Given], flags: Mapping[str, float]) -> Scenes:
    """A car on a banked curve, seen from behind, at the stated bank angle: the rig
    ``force_pictures`` draws for a request to see its forces."""
    from app.modules.physics.force_rigs import banked_curve_picture

    angle = values["angle"]
    deg = to_si(angle.value, angle.unit, expected_key="angle")
    picture = banked_curve_picture(round(math.degrees(deg), 6)) if 0 < deg < math.pi / 2 else None
    return [picture[0]] if picture is not None else []


def _standing(values: Mapping[str, Given], flags: Mapping[str, float]) -> Scenes:
    """A string fixed at both ends in its nth harmonic: ``standing_scene`` needs only the
    length and the harmonic, never the wave's speed the question may not state."""
    length = values["L"]
    scene = standing_scene(
        to_si(length.value, length.unit, expected_key="L"),
        int(flags.get("harmonic", 1)),
        2.0,
        pipe=False,
    )
    return [scene] if scene is not None else []


_SPEED, _ANGLE, _LENGTH, _MASS = "m/s", "°", "m", "kg"

SCENES: dict[str, SceneKind] = {
    "projectile": SceneKind(
        {
            "speed": Part("v0", _SPEED),
            "angle": Part("angle", _ANGLE),
            "height": Part("h0", _LENGTH, required=False),
            "g": Part("g", "m/s^2", required=False),
        },
        _solved("projectile", "time_of_flight"),
    ),
    "incline": SceneKind(
        {
            "angle": Part("angle", _ANGLE),
            "friction": Part("mu", ""),
            "mass": Part("m", _MASS, required=False, whole=False),
            "g": Part("g", "m/s^2", required=False),
        },
        _solved("friction", "incline_acceleration", {"motion_sign": (1.0, "")}),
    ),
    "atwood": SceneKind(
        {"mass1": Part("m1", _MASS), "mass2": Part("m2", _MASS)},
        _solved("force", "atwood"),
    ),
    "collision": SceneKind(
        {
            "mass1": Part("m1", _MASS),
            "speed1": Part("v1", _SPEED),
            "mass2": Part("m2", _MASS),
            "speed2": Part("v2", _SPEED, required=False),
        },
        _solved("momentum", "final_velocity", {"v2": (0.0, "m/s")}),
        claims={"sticks": ("elastic", 0.0), "elastic": ("elastic", 1.0)},
        bodies=(("mass1", "speed1"), ("mass2", "speed2")),
    ),
    "spring": SceneKind(
        {"spring_constant": Part("k", "N/m"), "mass": Part("m", _MASS)},
        _solved("spring", "shm_period"),
    ),
    "pendulum": SceneKind({"length": Part("L", _LENGTH)}, _solved("spring", "pendulum_period")),
    "orbit": SceneKind(
        {
            "altitude": Part("altitude", "km"),
            "planet_mass": Part("M", _MASS, required=False),
            "planet_radius": Part("radius_body", "km", required=False),
        },
        _solved("gravitation", "orbital_velocity"),
    ),
    "refraction": SceneKind(
        {
            "angle": Part("angle", _ANGLE),
            "index": Part("n2", ""),
            "index_from": Part("n1", "", required=False),
        },
        _solved("optics", "snell_refraction_angle", {"n1": (1.0, "")}),
    ),
    "lens": SceneKind(
        {
            "focal_length": Part("focal", _LENGTH),
            "object_distance": Part("d_obj", _LENGTH),
            "object_height": Part("", _LENGTH, required=False),
        },
        _solved("optics", "image_distance"),
    ),
    "standing_wave": SceneKind({"length": Part("L", _LENGTH)}, _standing),
    "banked_curve": SceneKind({"angle": Part("angle", _ANGLE)}, _banked),
}
