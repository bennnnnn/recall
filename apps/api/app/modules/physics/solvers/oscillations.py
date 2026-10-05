"""Oscillation solvers: F = kx, U = kx^2/2, T = 2 pi sqrt(m/k), and the pendulum's
T = 2 pi sqrt(L/g), which is the same oscillation and so lives here.
"""

from __future__ import annotations

import math

from app.models.schemas.math import GraphBlockSpec
from app.models.schemas.physics import PhysicsIntent, SimulationBlockSpec, SimulationBody
from app.modules.physics.solvers.common import (
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
    gravity_of,
)
from app.services.solving import SolveServiceError

_SAMPLES = 100


def _displacement_samples(t_period: float, amplitude: float) -> list[list[float]]:
    """Two periods of x(t) = A cos(2πt/T), uniform in time."""
    span = 2 * t_period
    dt = span / (_SAMPLES - 1)
    return [
        [round(i * dt, 4), round(amplitude * math.cos(2 * math.pi * (i * dt) / t_period), 4)]
        for i in range(_SAMPLES)
    ]


def _spring_scene(samples: list[list[float]], amplitude: float) -> SimulationBlockSpec:
    """The mass walks the same displacement the graph plotted.

    The graph's y column is position. The scene uses that column as x and
    holds y, so a frame cannot sit somewhere the curve is not. The wall is
    one amplitude left of the leftmost sample: close enough to read as a
    spring, far enough that the coil never collapses onto the mass.
    """
    xs = [point[1] for point in samples]
    radius = max(amplitude * 0.16, 0.02)
    wall = min(xs) - amplitude
    pad = amplitude * 0.45
    return SimulationBlockSpec(
        type="spring",
        bodies=[
            SimulationBody(
                path=[[x, round(radius, 4)] for x in xs],
                radius=radius,
            )
        ],
        x_min=wall - pad,
        x_max=max(xs) + pad,
        y_min=0.0,
        y_max=max(amplitude, radius * 4),
        ground=True,
        anchor=[wall, round(radius, 4)],
    )


def _oscillation_curve(t_period: float, amplitude: float | None) -> GraphBlockSpec:
    """One period-and-a-bit of x(t) = A cos(2πt/T).

    The oscillation is the thing worth seeing, so hand P3's player a curve.
    Amplitude only scales the y-axis — the shape and the period are what the
    question is about — so when none is given the plot is normalised rather
    than invented.
    """
    a_plot = abs(amplitude) if amplitude else 1.0
    points = _displacement_samples(t_period, a_plot)
    span = points[-1][0]
    return GraphBlockSpec(
        type="trajectory",
        expr=f"x(t) = {a_plot:g}*cos(2*pi*t/{t_period:.4g})",
        variable="t",
        x_min=0.0,
        x_max=span,
        points=points,
        title="Displacement vs. Time",
        x_label="Time (s)",
        y_label="Displacement (m)" if amplitude else "Displacement (normalised)",
        trajectory_type="position_vs_time",
    )


def _motion(
    t_period: float, amplitude: float | None
) -> tuple[GraphBlockSpec, list[SimulationBlockSpec]]:
    """Graph always. A scene only when the amplitude is a stated length.

    A normalised plot uses A = 1 so the shape is visible. Drawing that 1 as
    metres would invent a swing the question never gave.
    """
    graph = _oscillation_curve(t_period, amplitude)
    if amplitude is None or amplitude == 0:
        return graph, []
    return graph, [_spring_scene(graph.points, abs(amplitude))]


def solve_spring(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "spring_force"

    # A pendulum has a length, not a spring constant, so it is answered before
    # the k lookup below rather than after it.
    if op == "pendulum_period":
        length = p["L"]
        if length <= 0:
            raise SolveServiceError("pendulum length must be positive")
        g = gravity_of(p)
        if g <= 0:
            raise SolveServiceError("gravity must be positive")
        t_period = 2 * math.pi * math.sqrt(length / g)
        answer = (
            rf"T = 2\pi\sqrt{{\frac{{L}}{{g}}}} = 2\pi\sqrt{{\frac{{{length:g}}}{{{g:g}}}}} "
            rf"\approx {t_period:.2f} \text{{ s}}"
        )
        graph, scene = _motion(t_period, p.get("x"))
        return PhysicsResult(
            answer=answer,
            formulas=(r"T = 2\pi\sqrt{\frac{L}{g}}",),
            substitutions=(rf"T = 2\pi\sqrt{{\frac{{{length:g}}}{{{g:g}}}}}",),
            quantities=(QuantityResult("", t_period, "s"),),
            graph_specs=[graph],
            simulation_specs=scene,
        )

    # Like the pendulum above, these need no spring constant, so they are
    # answered before the k lookup rather than after it.
    if op == "shm_frequency":
        t_period = p["period"]
        if t_period <= 0:
            raise SolveServiceError("period must be positive")
        freq = 1 / t_period
        graph, scene = _motion(t_period, p.get("x"))
        return PhysicsResult(
            answer=(
                rf"f = \frac{{1}}{{T}} = \frac{{1}}{{{t_period:g}}} "
                rf"\approx {freq:.2f} \text{{ Hz}}"
            ),
            formulas=(r"f = \frac{1}{T}",),
            substitutions=(rf"f = \frac{{1}}{{{t_period:g}}}",),
            quantities=(QuantityResult("", freq, "Hz"),),
            graph_specs=[graph],
            simulation_specs=scene,
        )

    if op == "shm_max_speed":
        amplitude = p["x"]
        omega = p["omega"]
        if amplitude <= 0 or omega <= 0:
            raise SolveServiceError("amplitude and angular frequency must be positive")
        v_max = amplitude * omega
        graph, scene = _motion(2 * math.pi / omega, amplitude)
        return PhysicsResult(
            answer=(
                rf"v_{{max}} = A\omega = {amplitude:g} \cdot {omega:g} "
                rf"\approx {v_max:.2f} \text{{ m/s}}"
            ),
            formulas=(r"v_{max} = A\omega",),
            substitutions=(rf"v_{{max}} = {amplitude:g} \cdot {omega:g}",),
            quantities=(QuantityResult("", v_max, "m/s"),),
            graph_specs=[graph],
            simulation_specs=scene,
        )

    k = p["k"]
    if k <= 0:
        raise SolveServiceError("spring constant must be positive")

    if op == "spring_force":
        x = p["x"]
        f_val = k * abs(x)
        return PhysicsResult(
            answer=(rf"F = kx = {k:g} \cdot {abs(x):g} \approx {f_val:.2f} \text{{ N}}"),
            formulas=(r"F = kx",),
            substitutions=(rf"F = {k:g} \cdot {abs(x):g}",),
            quantities=(QuantityResult("", f_val, "N"),),
        )

    if op == "spring_energy":
        x = p["x"]
        u_val = 0.5 * k * x * x
        return PhysicsResult(
            answer=(
                rf"U = \tfrac{{1}}{{2}} k x^2 = 0.5 \cdot {k:g} \cdot "
                rf"{_latex_num(x, square=True)} \approx {u_val:.2f} \text{{ J}}"
            ),
            formulas=(r"U = \tfrac{1}{2} k x^2",),
            substitutions=(rf"E_s = 0.5 \cdot {k:g} \cdot {_latex_num(x, square=True)}",),
            quantities=(QuantityResult("", u_val, "J"),),
        )

    if op == "shm_period":
        m = p["m"]
        if m <= 0:
            raise SolveServiceError("mass must be positive")
        t_period = 2 * math.pi * math.sqrt(m / k)
        answer = (
            rf"T = 2\pi\sqrt{{\frac{{m}}{{k}}}} = 2\pi\sqrt{{\frac{{{m:g}}}{{{k:g}}}}} "
            rf"\approx {t_period:.2f} \text{{ s}}"
        )

        graph, scene = _motion(t_period, p.get("x"))
        return PhysicsResult(
            answer=answer,
            formulas=(r"T = 2\pi\sqrt{\frac{m}{k}}",),
            substitutions=(rf"T = 2\pi\sqrt{{\frac{{{m:g}}}{{{k:g}}}}}",),
            quantities=(QuantityResult("", t_period, "s"),),
            graph_specs=[graph],
            simulation_specs=scene,
        )

    raise SolveServiceError(f"unsupported spring op: {op}")
