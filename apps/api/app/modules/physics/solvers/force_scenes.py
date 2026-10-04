"""Scenes for force questions: a free-body diagram, an Atwood machine and a vector sum."""

from __future__ import annotations

import math

from app.models.schemas.physics import SimulationBlockSpec, SimulationBody, SimulationVector
from app.modules.physics.display import GIVEN_FIGURES, plain_number


def _free_body_scene(
    vectors: list[SimulationVector],
    *,
    label: str | None = None,
    ground: bool = False,
    position: tuple[float, float] = (0.0, 0.0),
) -> list[SimulationBlockSpec]:
    """A block with labelled forces on it, and nothing moving.

    The picture a force question actually wants. Every arrow is drawn at the
    length the renderer gives it rather than scaled by magnitude — a 59 N
    tension against a 49 N weight would differ by a fifth of an arrowhead, so
    the *labels* carry the sizes and the arrows carry the directions.
    """
    reach = 2.0
    points = [position, *((vector.anchor[0], vector.anchor[1]) for vector in vectors)]
    points.extend(
        (vector.anchor[0] + vector.dx, vector.anchor[1] + vector.dy) for vector in vectors
    )
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    return [
        SimulationBlockSpec(
            type="free_body",
            title="Free-Body Diagram",
            bodies=[
                SimulationBody(
                    path=[list(position), list(position)], radius=reach * 0.16, label=label
                )
            ],
            vectors=vectors,
            x_min=min(-reach, min(xs) - 1),
            x_max=max(reach, max(xs) + 1),
            y_min=min(-reach if not ground else -reach * 0.35, min(ys) - 0.7),
            y_max=max(reach, max(ys) + 1),
            ground=ground,
        )
    ]


def _atwood_scene(m1: float, m2: float, accel: float, tension: float) -> list[SimulationBlockSpec]:
    """Two masses on one rope over a pulley, the heavy one descending.

    An Atwood machine is a picture by definition — the name is of an apparatus
    — and "2.45 m/s^2 and 36.79 N" gives no hint that the two masses move in
    opposite directions at the same rate, which is the whole idea.
    """
    reach = 3.0
    m1, m2 = sorted((m1, m2), reverse=True)
    accel = abs(accel)
    drop = reach * 0.5
    n_points = 50
    # Uniform in time, so the pair visibly accelerates. The drop is a display
    # choice; the acceleration profile is not.
    duration = math.sqrt(2 * drop / accel) if accel > 0 else 1.0
    dt = duration / (n_points - 1)
    fall = [min(0.5 * accel * (i * dt) ** 2, drop) for i in range(n_points)]

    heavy = [[-1.0, round(reach - s, 4)] for s in fall]
    light = [[1.0, round(reach - drop + s, 4)] for s in fall]
    return [
        SimulationBlockSpec(
            type="free_body",
            duration_s=duration if accel > 0 else None,
            title="Atwood Machine",
            bodies=[
                SimulationBody(
                    path=heavy,
                    radius=0.4,
                    label=f"{plain_number(m1, GIVEN_FIGURES)} kg",
                    role="primary",
                ),
                SimulationBody(
                    path=light,
                    radius=0.4 * (m2 / m1) ** (1 / 3),
                    label=f"{plain_number(m2, GIVEN_FIGURES)} kg",
                    role="secondary",
                ),
            ],
            vectors=[
                SimulationVector(
                    anchor=[0.0, reach + 0.55],
                    dx=0.0,
                    dy=-1.0,
                    label=f"T = {plain_number(tension)} N",
                    role="result",
                )
            ],
            x_min=-reach * 0.8,
            x_max=reach * 0.8,
            y_min=0.0,
            y_max=reach + 1.2,
            # The pulley itself: a beam across the top with the rope's turning
            # point on it.
            beam=[-1.0, reach + 0.5, 1.0, reach + 0.5],
            pivot=[0.0, reach + 0.5],
        )
    ]


def _vector_sum_scene(
    parts: list[SimulationVector], result: SimulationVector
) -> list[SimulationBlockSpec]:
    """Components and their resultant, from one common tail.

    Here the arrows *are* scaled to magnitude, because a resultant that did not
    visibly out-reach its components would be the one picture that contradicts
    its own answer. The scene box is sized to the longest of them.
    """
    vectors = [*parts, result]
    reach = max(math.hypot(v.dx, v.dy) for v in vectors) * 1.3 or 1.0
    xs = [0.0, *(v.anchor[0] for v in vectors), *(v.anchor[0] + v.dx for v in vectors)]
    ys = [0.0, *(v.anchor[1] for v in vectors), *(v.anchor[1] + v.dy for v in vectors)]
    margin = reach * 0.2
    return [
        SimulationBlockSpec(
            type="vector_sum",
            title="Forces",
            vectors=vectors,
            x_min=min(xs) - margin,
            x_max=max(xs) + margin,
            y_min=min(ys) - margin,
            y_max=max(ys) + margin,
        )
    ]
