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


class SimulationBlockSpec(BaseModel):
    """A scene the client can play.

    ``arrows`` names the vectors worth drawing; the renderer derives each from
    the path rather than being handed components, so an arrow can never
    disagree with the motion it annotates.
    """

    type: Literal["projectile_motion", "orbit"]
    title: str | None = Field(default=None, max_length=64)
    bodies: list[SimulationBody] = Field(min_length=1, max_length=4)
    # World bounds. Named x_/y_ like GraphBlockSpec so the two read alike, but
    # these are a *scene* box: both axes are space, always.
    x_min: float = 0.0
    x_max: float = 10.0
    y_min: float = 0.0
    y_max: float = 10.0
    # gravity   — straight down from the body, constant
    # velocity  — tangent to the body's own path at the current frame
    # centripetal — from the body toward `centre`
    arrows: list[Literal["gravity", "velocity", "centripetal"]] = Field(
        default_factory=list, max_length=3
    )
    # The point an orbit turns about; required by a centripetal arrow, since
    # "toward the centre" is meaningless without one.
    centre: list[float] | None = None
    # Draw a ground line at y = 0. A projectile landing on nothing reads as a
    # dot drifting in a box.
    ground: bool = False

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
        # Every body is walked by one shared clock, so paths of different
        # lengths would drift apart on screen — a two-body scene would show a
        # collision at the wrong moment.
        lengths = {len(body.path) for body in self.bodies}
        if len(lengths) > 1:
            raise ValueError("every body must have the same number of samples")
        if not self.title:
            self.title = "Projectile" if self.type == "projectile_motion" else "Orbit"
        return self
