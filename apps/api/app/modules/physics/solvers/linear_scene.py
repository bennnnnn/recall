"""Native scenes for verified one-dimensional constant-acceleration motion."""

from __future__ import annotations

from app.models.schemas.physics.simulation import SimulationBlockSpec, SimulationBody


def linear_motion_scene(
    initial_velocity: float,
    acceleration: float,
    duration: float,
    *,
    height: float | None = None,
    ground: bool = False,
) -> list[SimulationBlockSpec]:
    if duration <= 0:
        return []
    values = [
        initial_velocity * (duration * i / 99) + 0.5 * acceleration * (duration * i / 99) ** 2
        for i in range(100)
    ]
    vertical = height is not None
    path = [[0.0, (height or 0.0) + value] if vertical else [value, 0.0] for value in values]
    xs, ys = [point[0] for point in path], [point[1] for point in path]
    ys_bounds = [*ys, 0.0] if ground else ys
    span = max(max(xs) - min(xs), max(ys_bounds) - min(ys_bounds), 1e-12)
    pad = 0.18 * span
    return [
        SimulationBlockSpec(
            type="projectile_motion" if vertical else "free_body",
            title="Vertical Motion" if vertical else "Straight-Line Motion",
            duration_s=duration if any(point != path[0] for point in path[1:]) else None,
            bodies=[SimulationBody(label="Body", radius=0.025 * span, path=path)],
            x_min=min(xs) - pad,
            x_max=max(xs) + pad,
            y_min=min(ys_bounds) - pad,
            y_max=max(ys_bounds) + pad,
            arrows=["gravity", "velocity"] if vertical else ["velocity"],
            ground=ground,
        )
    ]
