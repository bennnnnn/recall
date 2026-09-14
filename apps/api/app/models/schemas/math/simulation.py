"""The `simulation` fence — a scene of moving bodies, not an x-y plot.

P3 animated the trajectory *graph*, which answers "what shape is the path" but
not "what is actually moving, and what is pulling on it". Seven of the eleven
verified physics kinds draw nothing at all, and for several the picture is the
explanation: an orbiting dot is the most natural animation in the subject, and
a number cannot show a momentum transfer.

`GraphBlockSpec` cannot express any of that. It is an x-y plot with axes, one
curve and a pair of axis labels; a scene needs bodies with sizes, a ground, and
force vectors that point somewhere in the world rather than along an axis.

What is deliberately *not* here: velocities, masses, forces as numbers, or
anything else the renderer would have to do physics with. Every body carries a
**sampled path** in world units, exactly as the trajectory graph carries sampled
points, and the index is the clock. The client walks the array. Nothing on the
device re-derives motion — the same rule that governs the math pipeline.
"""

from __future__ import annotations

import math
import typing
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Matches GraphBlockSpec.points: the solver never legitimately needs more
# samples than the canonical solve produced.
MAX_PATH_POINTS = 500


class SimulationBody(BaseModel):
    """One moving object, as a sampled path through the scene.

    ``radius`` is in world units so a 2 kg ball and a 1 kg ball can be drawn at
    honest relative sizes; the renderer scales it with the rest of the scene.
    """

    label: str | None = Field(default=None, max_length=32)
    radius: float = Field(default=0.4, gt=0)
    path: list[list[float]] = Field(min_length=2, max_length=MAX_PATH_POINTS)
    # Named roles rather than colours: the client owns the palette, and a
    # hex code from the server would not survive a theme change.
    role: Literal["primary", "secondary"] = "primary"

    @model_validator(mode="after")
    def finite_pairs(self) -> SimulationBody:
        for point in self.path:
            if len(point) != 2 or not all(math.isfinite(value) for value in point):
                raise ValueError("every path sample must be a finite [x, y] pair")
        return self


SimulationType = Literal["projectile_motion", "orbit", "collision", "incline"]

# The one place a scene's `type` values are written down. Both the fence layer
# and the direct-reply guard have to tell a scene from a graph, and a fourth
# copy of this set living in each of them is precisely the drift the fence
# registry's docblock warns about — `sources` and `copy` were known to one list
# and not another for exactly that reason.
SIMULATION_SPEC_TYPES: frozenset[str] = frozenset(typing.get_args(SimulationType))

_DEFAULT_TITLES: dict[str, str] = {
    "projectile_motion": "Projectile",
    "orbit": "Orbit",
    "collision": "Collision",
    "incline": "Inclined Plane",
}


class SimulationBlockSpec(BaseModel):
    """A scene the client can play.

    ``arrows`` names the vectors worth drawing; the renderer derives each from
    the path rather than being handed components, so an arrow can never
    disagree with the motion it annotates. ``normal`` and ``friction`` are the
    exception and the reason ``incline_deg`` exists: a block that has not
    started moving has no tangent to read them off, and a free-body diagram of
    a stationary block is most of what an incline question wants.
    """

    type: SimulationType
    title: str | None = Field(default=None, max_length=64)
    bodies: list[SimulationBody] = Field(min_length=1, max_length=4)
    # World bounds. Named x_/y_ like GraphBlockSpec so the two read alike, but
    # these are a *scene* box: both axes are space, always.
    x_min: float = 0.0
    x_max: float = 10.0
    y_min: float = 0.0
    y_max: float = 10.0
    # gravity     — straight down from the body, constant (this is the weight)
    # velocity    — tangent to the body's own path at the current frame
    # centripetal — from the body toward `centre`
    # normal      — perpendicular to the slope, away from its surface
    # friction    — up the slope, opposing the slide
    arrows: list[Literal["gravity", "velocity", "centripetal", "normal", "friction"]] = Field(
        default_factory=list, max_length=5
    )
    # The point an orbit turns about; required by a centripetal arrow, since
    # "toward the centre" is meaningless without one.
    centre: list[float] | None = None
    # Draw a ground line at y = 0. A projectile landing on nothing reads as a
    # dot drifting in a box.
    ground: bool = False
    # The slope, in degrees, descending left to right. Draws the surface the
    # block sits on and fixes the normal and friction directions.
    incline_deg: float | None = Field(default=None, gt=-90.0, lt=90.0)

    @model_validator(mode="after")
    def coherent_scene(self) -> SimulationBlockSpec:
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("simulation requires ordered bounds")
        if not all(math.isfinite(v) for v in (self.x_min, self.x_max, self.y_min, self.y_max)):
            raise ValueError("simulation requires finite bounds")
        if "centripetal" in self.arrows and self.centre is None:
            raise ValueError("a centripetal arrow requires a centre")
        if self.centre is not None:
            if len(self.centre) != 2 or not all(math.isfinite(v) for v in self.centre):
                raise ValueError("centre must be a finite [x, y] pair")
        # Both are read off the slope, not off the motion, so neither can be
        # drawn without one — and a normal force pointing the wrong way is a
        # more confident lie than no arrow at all.
        if {"normal", "friction"} & set(self.arrows) and self.incline_deg is None:
            raise ValueError("normal and friction arrows require incline_deg")
        if self.incline_deg is not None and not math.isfinite(self.incline_deg):
            raise ValueError("incline_deg must be finite")
        # Every body is walked by one shared clock, so paths of different
        # lengths would drift apart on screen — a two-body scene would show a
        # collision at the wrong moment.
        lengths = {len(body.path) for body in self.bodies}
        if len(lengths) > 1:
            raise ValueError("every body must have the same number of samples")
        if not self.title:
            self.title = _DEFAULT_TITLES[self.type]
        return self
