"""Scenes for force questions: a free-body diagram, an Atwood machine and a vector sum."""

from __future__ import annotations

import math

from app.modules.physics.display import GIVEN_FIGURES, plain_number
from app.modules.physics.schemas import (
    SimulationAngle,
    SimulationBlockSpec,
    SimulationBody,
    SimulationPulley,
    SimulationSolid,
    SimulationTether,
    SimulationVector,
)
from app.modules.physics.schemas.simulation import TitleKey


def free_body_scene(
    vectors: list[SimulationVector],
    *,
    label: str | None = None,
    ground: bool = False,
    position: tuple[float, float] = (0.0, 0.0),
    alt: str | None = None,
    title: str = "Free-Body Diagram",
    title_key: TitleKey = "free_body",
    shape: str = "circle",
    solids: list[SimulationSolid] | None = None,
) -> list[SimulationBlockSpec]:
    """A block with labelled forces on it, and nothing moving.

    The picture a force question actually wants. A force's (dx, dy) is its
    size relative to the others: the renderer draws the longest at a fixed
    screen length, so the frame is sized by its direction alone. Only a
    `measure` (the h in mgh) is a length in the world.
    """
    points = [position, *((vector.anchor[0], vector.anchor[1]) for vector in vectors)]
    points.extend(_tip(vector) for vector in vectors)
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    # The frame and the block grow with the drawing. A 300 m climb in a box two
    # units wide was a vertical sliver with a dot on it.
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    reach = max(2.0, 0.3 * span)
    return [
        SimulationBlockSpec(
            type="free_body",
            title=title,
            title_key=title_key,
            bodies=[
                SimulationBody(
                    path=[list(position), list(position)],
                    radius=reach * 0.16,
                    label=label,
                    # A shape name from this file's table; the scene validates it.
                    shape=shape,  # type: ignore[arg-type]
                )
            ],
            vectors=vectors,
            solids=solids or [],
            x_min=min(-reach, min(xs) - 1),
            x_max=max(reach, max(xs) + 1),
            y_min=min(-reach if not ground else -reach * 0.35, min(ys) - 0.7),
            y_max=max(reach, max(ys) + 1),
            ground=ground,
            alt=alt,
        )
    ]


def _tip(vector: SimulationVector) -> tuple[float, float]:
    x, y = vector.anchor
    if vector.role == "measure":
        return x + vector.dx, y + vector.dy
    length = math.hypot(vector.dx, vector.dy)
    return x + vector.dx / length, y + vector.dy / length


def _atwood_scene(
    m1: float, m2: float, accel: float, tension: float | None = None
) -> list[SimulationBlockSpec]:
    """Two masses on one rope over a pulley, the heavy one descending.

    An Atwood machine is a picture by definition — the name is of an apparatus
    — and "2.45 m/s^2 and 36.79 N" gives no hint that the two masses move in
    opposite directions at the same rate, which is the whole idea. The rope
    runs from each mass up to the wheel's rim, the tension pulls up along it
    on both, and each mass carries its acceleration.
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

    wheel = 0.5
    axle = reach + 0.55
    heavy_size, light_size = 0.36, 0.36 * (m2 / m1) ** (1 / 3)
    heavy = [[-wheel, round(reach - 0.2 - s, 4)] for s in fall]
    light = [[wheel, round(reach - 0.2 - drop + s, 4)] for s in fall]
    vectors: list[SimulationVector] = []
    if tension is not None:
        shown = f"T = {plain_number(tension)} N"
        vectors += [
            SimulationVector(
                anchor=[0.0, heavy_size], dx=0.0, dy=1.0, label=shown, role="result", body=0
            ),
            # One rope, one tension: the second arrow says "T" and leaves the
            # number to the first, so the light side is not a stack of text.
            SimulationVector(
                anchor=[0.0, light_size], dx=0.0, dy=1.0, label="T", role="result", body=1
            ),
        ]
    if accel > 0:
        shown_a = f"a = {plain_number(accel)} m/s²"
        vectors += [
            SimulationVector(
                anchor=[-heavy_size - 0.25, 0.0],
                dx=0.0,
                dy=-1.0,
                label=shown_a,
                role="motion",
                body=0,
            ),
            SimulationVector(
                anchor=[light_size + 0.25, 0.0], dx=0.0, dy=1.0, role="motion", body=1
            ),
        ]
    heavy_label = f"{plain_number(m1, GIVEN_FIGURES)} kg"
    light_label = f"{plain_number(m2, GIVEN_FIGURES)} kg"
    return [
        SimulationBlockSpec(
            type="free_body",
            title="Atwood Machine",
            title_key="atwood",
            bodies=[
                SimulationBody(
                    path=heavy, radius=heavy_size, label=heavy_label, role="primary", shape="box"
                ),
                SimulationBody(
                    path=light, radius=light_size, label=light_label, role="secondary", shape="box"
                ),
            ],
            pulley=SimulationPulley(centre=[0.0, axle], radius=wheel),
            tethers=[
                SimulationTether(anchor=[-wheel, axle], body=0),
                SimulationTether(anchor=[wheel, axle], body=1),
            ],
            vectors=vectors,
            x_min=-reach * 0.8,
            x_max=reach * 0.8,
            y_min=0.0,
            y_max=axle + wheel + 0.4,
            alt=(
                f"Masses of {heavy_label} and {light_label} on a rope over a pulley; "
                f"the {heavy_label} one falls"
                + (f" at {plain_number(accel)} m/s²." if accel > 0 else ".")
            ),
        )
    ]


def _vector_sum_scene(
    parts: list[SimulationVector], result: SimulationVector, *, alt: str | None = None
) -> list[SimulationBlockSpec]:
    """Components and their resultant, from one common tail.

    Here the arrows *are* scaled to magnitude, because a resultant that did not
    visibly out-reach its components would be the one picture that contradicts
    its own answer. The scene box is sized to the longest of them, and the
    resultant's direction is an arc from the first component.
    """
    vectors = [*parts, result]
    reach = max(math.hypot(v.dx, v.dy) for v in vectors) * 1.3 or 1.0
    xs = [0.0, *(v.anchor[0] for v in vectors), *(v.anchor[0] + v.dx for v in vectors)]
    ys = [0.0, *(v.anchor[1] for v in vectors), *(v.anchor[1] + v.dy for v in vectors)]
    margin = reach * 0.2
    first = math.degrees(math.atan2(parts[0].dy, parts[0].dx)) if parts else 0.0
    direction = math.degrees(math.atan2(result.dy, result.dx))
    angles = (
        [
            SimulationAngle(
                vertex=list(result.anchor),
                start_deg=first,
                end_deg=direction,
                label=f"{plain_number(abs(direction - first))}°",
                role="result",
            )
        ]
        if abs(direction - first) >= 1.0
        else []
    )
    return [
        SimulationBlockSpec(
            type="vector_sum",
            title="Forces",
            title_key="forces",
            vectors=vectors,
            angles=angles,
            x_min=min(xs) - margin,
            x_max=max(xs) + margin,
            y_min=min(ys) - margin,
            y_max=max(ys) + margin,
            alt=alt,
        )
    ]


def resolution_scene(
    *,
    size: float,
    x_value: float,
    y_value: float,
    unit: str,
    base_deg: float,
    angle_deg: float,
    alt: str,
) -> list[SimulationBlockSpec]:
    """A vector and its two components, drawn in that order (``SimulationVector.stage``).

    The vector comes first, from the origin, with its angle marked from the axis the question
    measured it from (``base_deg``: east 0, north 90, west 180, south -90) and labelled as
    the question gave it; then the component along that axis grows from the same tail, and
    last the other runs from its end to the vector's tip, closing the triangle. A vector
    along an axis has one component, itself, so none is drawn over it.
    """
    vector = SimulationVector(
        anchor=[0.0, 0.0],
        dx=x_value,
        dy=y_value,
        label=f"{plain_number(size, GIVEN_FIGURES)}{unit}"[:24],
        role="force",
        stage=0,
    )
    across, up = abs(x_value) > 1e-9 * size, abs(y_value) > 1e-9 * size
    horizontal = SimulationVector(
        anchor=[0.0, 0.0],
        dx=x_value,
        dy=0.0,
        label=f"{plain_number(x_value)}{unit}"[:24],
        role="result",
        stage=1,
    )
    vertical = SimulationVector(
        anchor=[x_value, 0.0],
        dx=0.0,
        dy=y_value,
        label=f"{plain_number(y_value)}{unit}"[:24],
        role="result",
        stage=2,
    )
    if abs(base_deg) == 90.0:
        # Measured from the vertical: the vertical side rises from the tail first, so the
        # angle sits between two drawn lines, then the horizontal side runs to the tip
        # (owner, 2026-11-20: a 40° arc from the vertical hung beside no line).
        vertical = vertical.model_copy(update={"anchor": [0.0, 0.0], "stage": 1})
        horizontal = horizontal.model_copy(update={"anchor": [0.0, y_value], "stage": 2})
        parts = [vertical, horizontal]
    else:
        parts = [horizontal, vertical]
    if not (across and up):
        parts = []
    direction = math.degrees(math.atan2(y_value, x_value))
    # The short way from the axis to the vector, unless the question's angle is the long way
    # (a bearing of 300°): the arc sweeps what the question measured.
    sweep = (direction - base_deg + 180.0) % 360.0 - 180.0
    if abs(abs(sweep) - angle_deg % 360.0) > 0.5 and sweep != 0.0:
        sweep -= math.copysign(360.0, sweep)
    angles = (
        [
            SimulationAngle(
                vertex=[0.0, 0.0],
                start_deg=base_deg,
                end_deg=base_deg + sweep,
                label=f"{plain_number(angle_deg, GIVEN_FIGURES)}°",
                stage=0,
            )
        ]
        if abs(sweep) >= 1.0
        else []
    )
    margin = size * 0.25
    xs, ys = (0.0, x_value), (0.0, y_value)
    return [
        SimulationBlockSpec(
            type="vector_sum",
            title="Components",
            title_key="components",
            vectors=[vector, *parts],
            angles=angles,
            x_min=min(xs) - margin,
            x_max=max(xs) + margin,
            y_min=min(ys) - margin,
            y_max=max(ys) + margin,
            alt=alt,
        )
    ]
