"""A block's weight on a slope resolved into its two components, drawn on the slope's picture.

"Draw a free-body diagram showing ... the components of gravitational force parallel and
perpendicular to the incline" is what a textbook draws beside nearly every incline problem:
mg, N and f, and mg split into mg sin θ down the slope and mg cos θ into it. The slope's
picture (``solvers.friction.incline_scene``) draws the forces; a read that says the question
asks for the components (``"components": true``) adds the two parts, after the forces, the
part along the slope first. Their sizes are the server's: mg sin θ and mg cos θ of the
slope's own angle and, when the reader read them, the block's mass and g; with no mass the
parts carry their symbols only. A picture of anything but a block on a slope gets none.
"""

from __future__ import annotations

import math

from app.modules.physics.display import GIVEN_FIGURES, plain_number
from app.modules.physics.schemas import SimulationBlockSpec, SimulationVector

_INCLINE = "incline"
# Already drawn: the part along the slope a solve asked for ("mg sin θ = 49.05 N").
_ALONG = "mg sin"
# ``SimulationVector.label``'s most characters.
_LABEL_MAX = 24


def with_weight_parts(
    spec: SimulationBlockSpec, mass: float | None = None, g: float | None = None
) -> SimulationBlockSpec:
    """``spec`` with its block's weight resolved along and into the slope; ``spec`` as it is
    when it is no slope's picture. ``mass`` in kg and ``g`` in m/s² label the parts' sizes."""
    if spec.type != _INCLINE or not spec.incline_deg or not spec.bodies:
        return spec
    deg = abs(spec.incline_deg)
    theta = math.radians(deg)
    shown = f"{plain_number(deg, GIVEN_FIGURES)}°"
    weight = mass * g if mass and g else None
    # The slope falls to the right: down it is (cos θ, -sin θ), into it (-sin θ, -cos θ).
    parts = [
        ("sin", math.sin(theta), (math.cos(theta), -math.sin(theta))),
        ("cos", math.cos(theta), (-math.sin(theta), -math.cos(theta))),
    ]
    drawn = [v for v in spec.vectors if not (v.label or "").startswith(_ALONG)]
    stage = 1 + max((v.stage for v in drawn if v.stage is not None), default=-1)
    vectors = list(drawn)
    for offset, (trig, share, (dx, dy)) in enumerate(parts):
        size = f" = {plain_number(weight * share)} N" if weight else ""
        # The longest label an arrow carries; past it, the size, then the angle, give way.
        labels = (f"mg {trig} {shown}{size}", f"mg {trig} {shown}", f"mg {trig} θ")
        vectors.append(
            SimulationVector(
                anchor=[0.0, 0.0],
                dx=round(dx * share, 6),
                dy=round(dy * share, 6),
                label=next(label for label in labels if len(label) <= _LABEL_MAX),
                role="result",
                body=0,
                stage=min(stage + offset, 5),
            )
        )
    return spec.model_copy(update={"vectors": vectors})
