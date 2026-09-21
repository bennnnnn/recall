"""Circular motion, torque, equilibrium, and rotational mechanics."""

from __future__ import annotations

import math

from app.models.schemas.physics import (
    PhysicsIntent,
    SimulationBlockSpec,
    SimulationBody,
    SimulationVector,
)
from app.services.physics.solvers.common import (
    PhysicsResult,
    _latex_num,
    _params_in_si,
)
from app.services.solving import MathServiceError


def _orbit_scene(r: float) -> SimulationBlockSpec:
    """One lap, sampled at a constant angular step.

    Every circular answer is a number about something going round, and going
    round is the one motion a still picture cannot show at all — which is why
    this kind drew nothing before P14 and why it is the first scene after
    projectiles. The index is the clock here as everywhere else: a constant
    angular step is a constant speed, which is what uniform circular motion is.
    """
    n_points = 96
    path = [
        [
            round(r * math.cos(2 * math.pi * i / (n_points - 1)), 4),
            round(r * math.sin(2 * math.pi * i / (n_points - 1)), 4),
        ]
        for i in range(n_points)
    ]
    margin = r * 1.35
    return SimulationBlockSpec(
        type="orbit",
        title="Circular Motion",
        bodies=[SimulationBody(path=path, radius=r * 0.08)],
        x_min=-margin,
        x_max=margin,
        y_min=-margin,
        y_max=margin,
        arrows=["velocity", "centripetal"],
        centre=[0.0, 0.0],
    )


def solve_circular(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "centripetal_acceleration"
    if op == "angular_velocity" and "rpm" in p:
        omega_val = p["rpm"] * 2 * math.pi / 60
        return PhysicsResult(
            answer=(
                rf"\omega = n\frac{{2\pi}}{{60}} = {p['rpm']:g}\cdot\frac{{2\pi}}{{60}} "
                rf"\approx {omega_val:.2f} \text{{ rad/s}}"
            ),
            answer_value=f"{omega_val:.2f} rad/s",
        )
    r = p["r"]
    omega = p.get("omega")
    v = p.get("v", abs(omega) * r if omega is not None else 0.0)
    if r <= 0:
        raise MathServiceError("radius must be positive")

    scene = [_orbit_scene(r)]

    if op == "orbital_period":
        if v == 0:
            raise MathServiceError("period needs a nonzero speed")
        t_val = 2 * math.pi * r / abs(v)
        return PhysicsResult(
            answer=(
                rf"T = \frac{{2\pi r}}{{v}} = \frac{{2\pi \cdot {r:g}}}{{{v:g}}} "
                rf"\approx {t_val:.2f} \text{{ s}}"
            ),
            answer_value=f"{t_val:.2f} s",
            simulation_specs=scene,
        )

    if op == "angular_velocity":
        omega_val = abs(omega) if omega is not None else abs(v) / r
        return PhysicsResult(
            answer=(
                rf"\omega = \frac{{v}}{{r}} = \frac{{{abs(v):g}}}{{{r:g}}} "
                rf"\approx {omega_val:.2f} \text{{ rad/s}}"
            ),
            answer_value=f"{omega_val:.2f} rad/s",
            simulation_specs=scene,
        )

    a_c = v * v / r
    if op == "centripetal_acceleration":
        formula = (
            rf"a_c = \omega^2 r = {_latex_num(omega or 0, square=True)} \cdot {r:g}"
            if omega is not None
            else rf"a_c = \frac{{v^2}}{{r}} = \frac{{{_latex_num(v, square=True)}}}{{{r:g}}}"
        )
        return PhysicsResult(
            answer=(rf"{formula} \approx {a_c:.2f} \text{{ m/s}}^2"),
            answer_value=f"{a_c:.2f} m/s^2",
            simulation_specs=scene,
        )

    if op == "centripetal_force":
        if "m" not in p:
            raise MathServiceError("centripetal force needs a mass")
        f_val = p["m"] * a_c
        working = (
            rf"F_c = m\omega^2r = {p['m']:g} \cdot "
            rf"{_latex_num(omega or 0, square=True)} \cdot {r:g}"
            if omega is not None
            else rf"F_c = \frac{{m v^2}}{{r}} = "
            rf"\frac{{{p['m']:g} \cdot {_latex_num(v, square=True)}}}{{{r:g}}}"
        )
        return PhysicsResult(
            answer=rf"{working} \approx {f_val:.2f} \text{{ N}}",
            answer_value=f"{f_val:.2f} N",
            simulation_specs=scene,
        )

    raise MathServiceError(f"unsupported circular op: {op}")


# ---------------------------------------------------------------------------
# Springs: F = k x, U = 1/2 k x^2, T = 2 pi sqrt(m/k)
# A pendulum is the same oscillation with T = 2 pi sqrt(L/g), so it lives here
# rather than in a kind of its own.
# ---------------------------------------------------------------------------


def _lever_scene(loads: list[tuple[float, float, str, bool]]) -> list[SimulationBlockSpec]:
    """A beam on a wedge with a labelled force hanging at each arm.

    The see-saw is how this topic is taught and the one picture that makes
    "written order is not ownership" — the pairing bug P9 found — obvious at a
    glance: the arm each force actually has is drawn where it is, so a diagram
    reading 2 m under the wrong force would be visible rather than silent.

    Each load is (signed distance from the pivot, magnitude, label, is_answer).
    A negative distance is the left arm.
    """
    if not loads:
        return []
    reach = max(abs(d) for d, *_ in loads) * 1.25 or 1.0
    # Arrows hang below the beam, so the box needs room under it as well as a
    # little air above.
    depth = reach * 0.55
    return [
        SimulationBlockSpec(
            type="lever",
            title="Moments",
            beam=[-reach, 0.0, reach, 0.0],
            pivot=[0.0, 0.0],
            vectors=[
                SimulationVector(
                    anchor=[distance, 0.0],
                    dx=0.0,
                    dy=-1.0,
                    label=label,
                    role="result" if is_answer else "force",
                )
                for distance, _magnitude, label, is_answer in loads
            ],
            x_min=-reach * 1.15,
            x_max=reach * 1.15,
            y_min=-depth,
            y_max=depth,
        )
    ]


def solve_torque(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "torque"

    if op == "moment_balance":
        if "d2" in p and "F2" not in p:
            f1, d1, d2 = p["F1"], p["d1"], p["d2"]
            if d2 == 0:
                raise MathServiceError("balancing arm must be nonzero")
            f2 = f1 * d1 / d2
            return PhysicsResult(
                answer=(
                    r"F_1 d_1 = F_2 d_2 \Rightarrow F_2 = \frac{F_1 d_1}{d_2}"
                    rf" = \frac{{{f1:g} \cdot {d1:g}}}{{{d2:g}}} "
                    rf"\approx {f2:.2f} \text{{ N}}"
                ),
                answer_value=f"{f2:.2f} N",
                simulation_specs=_lever_scene(
                    [
                        (-d1, f1, f"{f1:g} N at {d1:g} m", False),
                        (d2, f2, f"{f2:.2f} N at {d2:g} m", True),
                    ]
                ),
            )
        uses_masses = "m1" in p and "m2" in p
        f1, d1, f2 = (p["m1"], p["d1"], p["m2"]) if uses_masses else (p["F1"], p["d1"], p["F2"])
        if f2 == 0:
            raise MathServiceError("balancing force must be nonzero")
        d2 = f1 * d1 / f2
        balance_formula = (
            r"m_1 g d_1 = m_2 g d_2 \Rightarrow d_2 = \frac{m_1 d_1}{m_2}"
            if uses_masses
            else r"F_1 d_1 = F_2 d_2 \Rightarrow d_2 = \frac{F_1 d_1}{F_2}"
        )
        return PhysicsResult(
            answer=(
                rf"{balance_formula} = \frac{{{f1:g} \cdot {d1:g}}}{{{f2:g}}} "
                rf"\approx {d2:.2f} \text{{ m}}"
            ),
            answer_value=f"{d2:.2f} m",
            # The known load on the left, the one whose arm was the question on
            # the right, so the answer is the arm you can see.
            simulation_specs=_lever_scene(
                [
                    (-d1, f1, f"{f1:g} {'kg' if uses_masses else 'N'} at {d1:g} m", False),
                    (d2, f2, f"{f2:g} {'kg' if uses_masses else 'N'} at {d2:.2f} m", True),
                ]
            ),
        )

    if op == "lever_arm":
        force = p["F"]
        if force == 0:
            raise MathServiceError("force must be nonzero to find a lever arm")
        distance = p["tau"] / force
        return PhysicsResult(
            answer=(
                r"\tau = Fd \Rightarrow d = \frac{\tau}{F} = "
                rf"\frac{{{p['tau']:g}}}{{{force:g}}} \approx {distance:.2f} \text{{ m}}"
            ),
            answer_value=f"{distance:.2f} m",
            simulation_specs=_lever_scene(
                [(distance, force, f"{force:g} N at {distance:.2f} m", True)]
            ),
        )

    if op == "net_torque":
        torques = [value for key, value in p.items() if key.startswith("tau")]
        if len(torques) < 2:
            raise MathServiceError("net torque needs at least two torques")
        net = sum(torques)
        net_direction = "counterclockwise" if net > 0 else "clockwise" if net < 0 else "balanced"
        terms = " + ".join(f"({value:g})" for value in torques)
        return PhysicsResult(
            answer=(
                rf"\tau_{{net}} = \sum \tau = {terms} \approx {net:.2f} "
                r"\text{ N}\cdot\text{m}"
            ),
            answer_value=(
                f"{abs(net):.2f} N*m ({net_direction})" if net else "0.00 N*m (balanced)"
            ),
        )

    if op == "torque":
        f, d = p["F"], p["d"]
        theta = p.get("angle")
        if theta is None:
            tau = f * d
            answer = (
                rf"\tau = F d = {f:g} \cdot {d:g} "
                rf"\approx {tau:.2f} \text{{ N}}\cdot\text{{m}}"
            )
            # Square on: straight down, which is what F d assumes.
            direction = (0.0, -1.0)
        else:
            tau = f * d * math.sin(theta)
            deg = math.degrees(theta)
            answer = (
                rf"\tau = F d \sin\theta = {f:g} \cdot {d:g} \cdot \sin({deg:g}^\circ) "
                rf"\approx {tau:.2f} \text{{ N}}\cdot\text{{m}}"
            )
            # Drawn at the angle it was given, so the sin theta in the formula
            # is the thing on screen rather than a factor to take on trust.
            direction = (math.cos(theta), -math.sin(theta))
        scene = _lever_scene([(d, f, f"{f:g} N at {d:g} m", True)])
        if scene:
            scene[0].vectors[0].dx, scene[0].vectors[0].dy = direction
        return PhysicsResult(answer=answer, answer_value=f"{tau:.2f} N*m", simulation_specs=scene)

    raise MathServiceError(f"unsupported torque op: {op}")


# ---------------------------------------------------------------------------
# Rotational dynamics
# ---------------------------------------------------------------------------


def solve_rotation(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "moment_of_inertia":
        factor = p["shape_factor"]
        value = factor * p["m"] * p["r"] ** 2
        return PhysicsResult(
            answer=(
                rf"I = {factor:g} m r^2 = {factor:g} \cdot {p['m']:g} \cdot "
                rf"{_latex_num(p['r'], square=True)} \approx {value:.2f} "
                rf"\text{{ kg}}\,\text{{m}}^2"
            ),
            answer_value=f"{value:.2f} kg*m^2",
        )

    if op == "angular_momentum":
        value = p["inertia"] * p["omega"]
        return PhysicsResult(
            answer=(
                rf"L = I\omega = {p['inertia']:g} \cdot {p['omega']:g} "
                rf"\approx {value:.2f} \text{{ kg}}\,\text{{m}}^2\text{{/s}}"
            ),
            answer_value=f"{value:.2f} kg*m^2/s",
        )

    if op == "rotational_kinetic_energy":
        value = 0.5 * p["inertia"] * p["omega"] ** 2
        return PhysicsResult(
            answer=(
                rf"E_k = \tfrac{{1}}{{2}} I \omega^2 = 0.5 \cdot {p['inertia']:g} \cdot "
                rf"{_latex_num(p['omega'], square=True)} \approx {value:.2f} \text{{ J}}"
            ),
            answer_value=f"{value:.2f} J",
        )

    if op == "angular_velocity":
        elapsed = p["t"]
        if elapsed <= 0:
            raise MathServiceError("elapsed time must be positive")
        value = p["theta"] / elapsed
        return PhysicsResult(
            answer=(
                rf"\omega = \frac{{\theta}}{{t}} = \frac{{{p['theta']:g}}}{{{elapsed:g}}} "
                rf"\approx {value:.2f} \text{{ rad/s}}"
            ),
            answer_value=f"{value:.2f} rad/s",
        )

    raise MathServiceError(f"unsupported rotation op: {op}")
