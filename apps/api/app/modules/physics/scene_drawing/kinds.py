"""The scenes a reply may describe, each confirmed by the physics readers and drawn by the
builder its solver draws with.

Each kind names its parts (a launch speed, a slope's angle, two masses), the unit each is
in, the readings of the physics readers that read its setup (``reads``: the operations
``extract_physics_intent`` reads such a question as), and the reader's values it is drawn
from (``setup``). A scene is drawn from the reader's own reading of the question: its launch
height and direction, its collision's type, its media's order, its planet. The reply's
description only has to agree with it. A kind no reader confirms is not listed: a spring
(the reader does not say whether it hangs or lies flat) and a standing wave (it does not
tell a string from a pipe) are not drawn.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from app.modules.physics.schemas import PhysicsIntent, SimulationBlockSpec
from app.modules.physics.solver import solve_physics
from app.modules.physics.solvers.si import to_si

logger = logging.getLogger(__name__)

Scenes = list[SimulationBlockSpec]
# The reader's values a scene is drawn from: parameter -> (value, unit).
Quantities = Mapping[str, tuple[float, str]]
Drawn = Callable[[Quantities], Scenes]


@dataclass(frozen=True)
class Part:
    """One value a scene takes: the reader's parameter ("" for a value the scene is checked
    with but does not draw, a lens's object height), a unit of its kind ("" for a pure
    number), and whether the scene can do without it."""

    param: str
    sample: str
    required: bool = True


@dataclass(frozen=True)
class SceneKind:
    parts: Mapping[str, Part]
    draw: Drawn
    # The readings of the question that read this setup (``extract_physics_intent``'s ops).
    reads: frozenset[str]
    # The reader's parameters the scene is drawn from.
    setup: tuple[str, ...]
    # The stated quantities the scene may leave aside, one each (a slope's length, a bob's
    # mass): any other one the parts do not use is another situation, and nothing is drawn.
    tolerates: tuple[str, ...] = ()
    # Parts that name the same bodies in either order (an Atwood machine's two masses).
    unordered: tuple[str, ...] = ()


def _solved(kind: str, op: str) -> Drawn:
    """The scene the solver for ``op`` draws from the reader's values, or none when it
    draws none (a value it cannot use, a situation it does not take)."""

    def draw(values: Quantities) -> Scenes:
        try:
            intent = PhysicsIntent.model_validate(
                {
                    "kind": kind,
                    "operation": "solve",
                    "physics_op": op,
                    "physics_params": {name: value for name, (value, _unit) in values.items()},
                    "physics_units": {name: unit for name, (_value, unit) in values.items()},
                }
            )
            return list(solve_physics(intent).simulation_specs)
        except Exception as exc:  # A scene that cannot be drawn is no picture.
            logger.info("described scene not drawn op=%s (%s)", op, type(exc).__name__)
            return []

    return draw


def _banked(values: Quantities) -> Scenes:
    """A car on a banked curve, seen from behind, at the bank angle the reader read: the
    rig ``force_pictures`` draws for a request to see its forces."""
    from app.modules.physics.force_rigs import banked_curve_picture

    value, unit = values["angle"]
    rad = to_si(value, unit, expected_key="angle")
    picture = banked_curve_picture(round(math.degrees(rad), 6)) if 0 < rad < math.pi / 2 else None
    return [picture[0]] if picture is not None else []


_SPEED, _ANGLE, _LENGTH, _MASS = "m/s", "°", "m", "kg"
_G = Part("g", "m/s^2", required=False)
_LAUNCHED = frozenset(
    {"range", "max_height", "time_of_flight", "impact_speed", "projectile_time_to_peak"}
)

SCENES: dict[str, SceneKind] = {
    "projectile": SceneKind(
        {
            "speed": Part("v0", _SPEED),
            # Left out only for a launch the question says is horizontal (the reader's 0°).
            "angle": Part("angle", _ANGLE, required=False),
            "height": Part("h0", _LENGTH, required=False),
            "g": _G,
        },
        _solved("projectile", "time_of_flight"),
        reads=_LAUNCHED,
        setup=("v0", "angle", "h0", "g"),
        tolerates=(_MASS,),
    ),
    "incline": SceneKind(
        {
            "angle": Part("angle", _ANGLE),
            "friction": Part("mu", ""),
            "mass": Part("m", _MASS, required=False),
            "g": _G,
        },
        _solved("friction", "incline_acceleration"),
        reads=frozenset({"incline_acceleration"}),
        setup=("angle", "mu", "m", "g", "motion_sign"),
        tolerates=(_LENGTH,),
    ),
    "atwood": SceneKind(
        {"mass1": Part("m1", _MASS), "mass2": Part("m2", _MASS), "g": _G},
        _solved("force", "atwood"),
        reads=frozenset({"atwood"}),
        setup=("m1", "m2", "g"),
        tolerates=(_LENGTH,),
        unordered=("mass1", "mass2"),
    ),
    "collision": SceneKind(
        {
            "mass1": Part("m1", _MASS),
            "speed1": Part("v1", _SPEED),
            "mass2": Part("m2", _MASS),
            "speed2": Part("v2", _SPEED, required=False),
        },
        _solved("momentum", "final_velocity"),
        reads=frozenset({"final_velocity"}),
        setup=("m1", "v1", "m2", "v2", "elastic"),
    ),
    "pendulum": SceneKind(
        {"length": Part("L", _LENGTH), "g": _G},
        _solved("spring", "pendulum_period"),
        reads=frozenset({"pendulum_period", "pendulum_frequency", "pendulum_bottom_speed"}),
        setup=("L", "g"),
        tolerates=(_MASS, _ANGLE),
    ),
    "orbit": SceneKind(
        {
            "altitude": Part("altitude", "km"),
            "planet_mass": Part("M", _MASS, required=False),
            "planet_radius": Part("radius_body", "km", required=False),
        },
        # The planet's mass and radius are the reader's: stated, or the body it names.
        _solved("gravitation", "orbital_velocity"),
        reads=frozenset({"orbital_velocity", "kepler_period_altitude"}),
        setup=("altitude", "M", "radius_body"),
        tolerates=(_MASS,),
    ),
    "refraction": SceneKind(
        {
            "angle": Part("angle", _ANGLE),
            "index": Part("n2", ""),
            "index_from": Part("n1", "", required=False),
        },
        _solved("optics", "snell_refraction_angle"),
        reads=frozenset({"snell_refraction_angle"}),
        setup=("n1", "n2", "angle", "from_surface"),
        tolerates=(_LENGTH,),
    ),
    "lens": SceneKind(
        {
            "focal_length": Part("focal", _LENGTH),
            "object_distance": Part("d_obj", _LENGTH),
            "object_height": Part("", _LENGTH, required=False),
        },
        _solved("optics", "image_distance"),
        reads=frozenset({"image_distance"}),
        setup=("focal", "d_obj"),
    ),
    "banked_curve": SceneKind(
        {"angle": Part("angle", _ANGLE), "g": _G},
        _banked,
        reads=frozenset({"banked_speed"}),
        setup=("angle",),
        tolerates=(_LENGTH, _MASS, _SPEED, ""),
    ),
}
