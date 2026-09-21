"""Forces, energy, momentum, collisions, and friction solvers."""

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


def _free_body_scene(
    vectors: list[SimulationVector],
    *,
    label: str | None = None,
    ground: bool = False,
) -> list[SimulationBlockSpec]:
    """A block with labelled forces on it, and nothing moving.

    The picture a force question actually wants. Every arrow is drawn at the
    length the renderer gives it rather than scaled by magnitude — a 59 N
    tension against a 49 N weight would differ by a fifth of an arrowhead, so
    the *labels* carry the sizes and the arrows carry the directions.
    """
    reach = 2.0
    return [
        SimulationBlockSpec(
            type="free_body",
            title="Free-Body Diagram",
            bodies=[
                SimulationBody(path=[[0.0, 0.0], [0.0, 0.0]], radius=reach * 0.16, label=label)
            ],
            vectors=vectors,
            x_min=-reach,
            x_max=reach,
            y_min=-reach if not ground else -reach * 0.35,
            y_max=reach,
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
            title="Atwood Machine",
            bodies=[
                SimulationBody(
                    path=heavy,
                    radius=0.3 * (m1 ** (1 / 3)),
                    label=f"{m1:g} kg",
                    role="primary",
                ),
                SimulationBody(
                    path=light,
                    radius=0.3 * (m2 ** (1 / 3)),
                    label=f"{m2:g} kg",
                    role="secondary",
                ),
            ],
            vectors=[
                SimulationVector(
                    anchor=[0.0, reach + 0.55],
                    dx=0.0,
                    dy=-1.0,
                    label=f"T = {tension:.2f} N",
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
    return [
        SimulationBlockSpec(
            type="vector_sum",
            title="Forces",
            vectors=vectors,
            x_min=-reach * 0.25,
            x_max=reach,
            y_min=-reach * 0.25,
            y_max=reach,
        )
    ]


def solve_force(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op

    # Rope shapes, answered before the F/m/a triangle below because their
    # answer is not m*a — which is exactly the confusion P2 refused rather
    # than let ship.
    if op == "tension":
        m = p["m"]
        if m <= 0:
            raise MathServiceError("mass must be positive")
        g = p.get("g", 9.81)
        a = p.get("a", 0.0)
        if a <= -g:
            raise MathServiceError("the rope goes slack at or beyond free fall")
        t_val = m * (g + a)
        return PhysicsResult(
            answer=(
                rf"T = m(g + a) = {m:g}({g:g} + {_latex_num(a)}) "
                rf"\approx {t_val:.2f} \text{{ N}}"
            ),
            answer_value=f"{t_val:.2f} N",
            # Two arrows and a mass is the whole of this problem, and seeing
            # them is what makes T = m(g + a) rather than m*a obvious: the rope
            # carries the weight *and* the acceleration.
            simulation_specs=_free_body_scene(
                [
                    SimulationVector(
                        anchor=[0.0, 0.0],
                        dx=0.0,
                        dy=1.0,
                        label=f"T = {t_val:.2f} N",
                        role="result",
                    ),
                    SimulationVector(
                        anchor=[0.0, 0.0],
                        dx=0.0,
                        dy=-1.0,
                        label=f"W = {m * g:.2f} N",
                    ),
                ],
                label=f"{m:g} kg",
            ),
        )

    if op == "resultant_force":
        f1, f2 = p["F1"], p["F2"]
        phi = p["angle"]  # radians (converted by _params_in_si)
        # The general parallelogram law. At phi = 90 degrees the cosine term
        # drops out and it reduces to Pythagoras, so the perpendicular case
        # needs no separate branch.
        r_val = math.sqrt(f1 * f1 + f2 * f2 + 2 * f1 * f2 * math.cos(phi))
        theta = math.degrees(math.atan2(f2 * math.sin(phi), f1 + f2 * math.cos(phi)))
        return PhysicsResult(
            answer=(
                rf"R = \sqrt{{F_1^2 + F_2^2 + 2F_1F_2\cos\phi}} = "
                rf"\sqrt{{{_latex_num(f1, square=True)} + {_latex_num(f2, square=True)} + "
                rf"2 \cdot {f1:g} \cdot {f2:g}\cos({math.degrees(phi):g}^\circ)}} "
                rf"\approx {r_val:.2f} \text{{ N}}, \quad "
                rf"\theta = \arctan\frac{{F_2\sin\phi}}{{F_1 + F_2\cos\phi}} "
                rf"= \arctan\frac{{{f2:g}\sin({math.degrees(phi):g}^\circ)}}"
                rf"{{{f1:g} + {f2:g}\cos({math.degrees(phi):g}^\circ)}} "
                rf"\approx {theta:.2f}^\circ"
            ),
            answer_value=f"{r_val:.2f} N at {theta:.2f}°",
            simulation_specs=_vector_sum_scene(
                [
                    SimulationVector(anchor=[0.0, 0.0], dx=f1, dy=0.0, label=f"{f1:g} N"),
                    SimulationVector(
                        anchor=[0.0, 0.0],
                        dx=f2 * math.cos(phi),
                        dy=f2 * math.sin(phi),
                        label=f"{f2:g} N",
                    ),
                ],
                SimulationVector(
                    anchor=[0.0, 0.0],
                    dx=r_val * math.cos(math.radians(theta)),
                    dy=r_val * math.sin(math.radians(theta)),
                    label=f"{r_val:.2f} N",
                    role="result",
                ),
            ),
        )

    if op == "resolve_force":
        f = p["F"]
        theta = p["angle"]  # radians
        fx = f * math.cos(theta)
        fy = f * math.sin(theta)
        return PhysicsResult(
            answer=(
                rf"F_x = F\cos\theta = {f:g}\cos({math.degrees(theta):g}^\circ) "
                rf"\approx {fx:.2f} \text{{ N}}, \quad "
                rf"F_y = F\sin\theta = {f:g}\sin({math.degrees(theta):g}^\circ) "
                rf"\approx {fy:.2f} \text{{ N}}"
            ),
            answer_value=f"{fx:.2f} N horizontally and {fy:.2f} N vertically",
            simulation_specs=_vector_sum_scene(
                [
                    SimulationVector(anchor=[0.0, 0.0], dx=fx, dy=0.0, label=f"{fx:.2f} N"),
                    SimulationVector(anchor=[fx, 0.0], dx=0.0, dy=fy, label=f"{fy:.2f} N"),
                ],
                SimulationVector(anchor=[0.0, 0.0], dx=fx, dy=fy, label=f"{f:g} N", role="result"),
            ),
        )

    if op == "atwood":
        m1, m2 = p["m1"], p["m2"]
        if m1 <= 0 or m2 <= 0:
            raise MathServiceError("masses must be positive")
        g = p.get("g", 9.81)
        a_val = (m1 - m2) * g / (m1 + m2)
        t_val = 2 * m1 * m2 * g / (m1 + m2)
        return PhysicsResult(
            answer=(
                rf"a = \frac{{(m_1 - m_2)g}}{{m_1 + m_2}} = "
                rf"\frac{{({m1:g} - {m2:g}) \cdot {g:g}}}{{{m1:g} + {m2:g}}} "
                rf"\approx {a_val:.2f} \text{{ m/s}}^2, \quad "
                rf"T = \frac{{2 m_1 m_2 g}}{{m_1 + m_2}} = "
                rf"\frac{{2 \cdot {m1:g} \cdot {m2:g} \cdot {g:g}}}{{{m1:g} + {m2:g}}} "
                rf"\approx {t_val:.2f} \text{{ N}}"
            ),
            answer_value=f"{a_val:.2f} m/s^2 and {t_val:.2f} N",
            simulation_specs=_atwood_scene(m1, m2, a_val, t_val),
        )

    if "F" in p and "m" in p and "a" not in p:
        a_val = p["F"] / p["m"]
        answer_latex = (
            rf"a = \frac{{F}}{{m}} = \frac{{{p['F']:g}}}{{{p['m']:g}}} "
            rf"\approx {a_val:.2f} \text{{ m/s}}^2"
        )
        answer_value = f"{a_val:.2f} m/s^2"
    elif "F" in p and "a" in p and "m" not in p:
        m_val = p["F"] / p["a"]
        answer_latex = (
            rf"m = \frac{{F}}{{a}} = \frac{{{p['F']:g}}}{{{p['a']:g}}} "
            rf"\approx {m_val:.2f} \text{{ kg}}"
        )
        answer_value = f"{m_val:.2f} kg"
    elif "m" in p and "a" in p and "F" not in p:
        f_val = p["m"] * p["a"]
        answer_latex = (
            rf"F = m \cdot a = {p['m']:g} \cdot {p['a']:g} "
            rf"\approx {f_val:.2f} \text{{ N}}"
        )
        answer_value = f"{f_val:.2f} N"
    else:
        raise MathServiceError("force solve needs exactly two of F, m, a")

    # F = ma is a push and the motion it produces, drawn the same way round.
    # Both point right by convention — the question states no direction, and
    # inventing opposing ones would say the block is being decelerated.
    force = p.get("F", p.get("m", 0.0) * p.get("a", 0.0))
    accel = p.get("a", p.get("F", 0.0) / p["m"] if p.get("m") else 0.0)
    scene = _free_body_scene(
        [
            SimulationVector(
                anchor=[0.0, 0.0], dx=1.0, dy=0.0, label=f"F = {force:.2f} N", role="result"
            ),
            SimulationVector(anchor=[0.0, -0.9], dx=1.0, dy=0.0, label=f"a = {accel:.2f} m/s²"),
        ],
        label=f"{p['m']:g} kg" if "m" in p else None,
    )
    return PhysicsResult(answer=answer_latex, answer_value=answer_value, simulation_specs=scene)


# ---------------------------------------------------------------------------
# Energy: KE = ½ m v², PE = m g h, W = F d, P = F v or W / t
# ---------------------------------------------------------------------------


def solve_energy(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    g = p.get("g", 9.81)
    op = intent.physics_op or "kinetic_energy"

    if op == "mechanical_efficiency":
        supplied = p["E_in"]
        output = p["E_out"]
        if supplied <= 0 or output < 0:
            raise MathServiceError("efficiency needs positive input and nonnegative output")
        eta = output / supplied
        answer_latex = (
            rf"\eta = \frac{{E_{{out}}}}{{E_{{in}}}} = "
            rf"\frac{{{output:g}}}{{{supplied:g}}} \approx {eta:.4g}"
        )
        answer_value = f"{eta:.4g} ({eta * 100:.4g}%)"
    elif op == "kinetic_energy":
        ke_val = 0.5 * p["m"] * p["v"] ** 2
        v_sq = _latex_num(p["v"], square=True)
        answer_latex = (
            rf"KE = \frac{{1}}{{2}} m v^2 = \frac{{1}}{{2}} \cdot {p['m']:g} \cdot {v_sq} "
            rf"\approx {ke_val:.2f} \text{{ J}}"
        )
        answer_value = f"{ke_val:.2f} J"
    elif op == "potential_energy":
        pe_val = p["m"] * g * p["h"]
        answer_latex = (
            rf"PE = m g h = {p['m']:g} \cdot {g:g} \cdot {p['h']:g} "
            rf"\approx {pe_val:.2f} \text{{ J}}"
        )
        answer_value = f"{pe_val:.2f} J"
    elif op == "work":
        w_val = p["F"] * p["d"]
        answer_latex = (
            rf"W = F \cdot d = {p['F']:g} \cdot {p['d']:g} "
            rf"\approx {w_val:.2f} \text{{ J}}"
        )
        answer_value = f"{w_val:.2f} J"
    elif op == "power":
        if "W" in p and "t" in p:
            # P = W / t — the other school form, when no force/velocity pair
            # was given ("100 J of work in 5 s").
            if p["t"] == 0:
                raise MathServiceError("power needs a nonzero time")
            power_val = p["W"] / p["t"]
            answer_latex = (
                rf"P = \frac{{W}}{{t}} = \frac{{{p['W']:g}}}{{{p['t']:g}}} "
                rf"\approx {power_val:.2f} \text{{ W}}"
            )
        else:
            power_val = p["F"] * p["v"]
            answer_latex = (
                rf"P = F \cdot v = {p['F']:g} \cdot {p['v']:g} "
                rf"\approx {power_val:.2f} \text{{ W}}"
            )
        answer_value = f"{power_val:.2f} W"
    else:
        raise MathServiceError(f"unsupported energy op: {op}")

    # Only where there is something spatial to show. A block with a "3 m/s"
    # arrow beside it tells you nothing the sentence did not — the height in
    # mgh and the distance in Fd are quantities you can point at, and a speed
    # is not, so kinetic energy and power get no picture rather than a
    # decorative one.
    scene: list[SimulationBlockSpec] = []
    if op == "potential_energy":
        height = p["h"]
        scene = _free_body_scene(
            [
                SimulationVector(
                    anchor=[0.0, 0.0], dx=0.0, dy=-1.0, label=f"W = {p['m'] * g:.2f} N"
                ),
                SimulationVector(
                    anchor=[-0.9, -height],
                    dx=0.0,
                    dy=height,
                    label=f"h = {height:g} m",
                    role="measure",
                ),
            ],
            label=f"{p['m']:g} kg",
            ground=True,
        )
    elif op == "work":
        distance = p["d"]
        scene = _free_body_scene(
            [
                SimulationVector(
                    anchor=[0.0, 0.0], dx=1.0, dy=0.0, label=f"F = {p['F']:g} N", role="result"
                ),
                SimulationVector(
                    anchor=[0.0, -0.8],
                    dx=distance,
                    dy=0.0,
                    label=f"d = {distance:g} m",
                    role="measure",
                ),
            ],
            ground=True,
        )
    return PhysicsResult(answer=answer_latex, answer_value=answer_value, simulation_specs=scene)


# ---------------------------------------------------------------------------
# Momentum: p = m v, impulse J = F dt (or m dv), 1D collisions
#   inelastic: v = (m1 v1 + m2 v2) / (m1 + m2)
#   elastic:   v1' = ((m1-m2) v1 + 2 m2 v2) / (m1+m2), v2' symmetric
# ---------------------------------------------------------------------------


def solve_momentum(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "momentum"

    if op == "center_of_mass":
        total_mass = p["m1"] + p["m2"]
        if p["m1"] <= 0 or p["m2"] <= 0 or total_mass <= 0:
            raise MathServiceError("center of mass needs positive masses")
        center = (p["m1"] * p["x1"] + p["m2"] * p["x2"]) / total_mass
        return PhysicsResult(
            answer=(
                r"x_{cm} = \frac{m_1x_1 + m_2x_2}{m_1 + m_2} = "
                rf"\frac{{{p['m1']:g} \cdot {p['x1']:g} + {p['m2']:g} \cdot {p['x2']:g}}}"
                rf"{{{p['m1']:g} + {p['m2']:g}}} \approx {center:.4g} \text{{ m}}"
            ),
            answer_value=f"{center:.4g} m",
        )

    if op == "momentum":
        p_val = p["m"] * p["v"]
        return PhysicsResult(
            answer=(
                rf"p = m v = {p['m']:g} \cdot {p['v']:g} "
                rf"\approx {p_val:.2f} \text{{ kg}}\cdot\text{{m/s}}"
            ),
            answer_value=f"{p_val:.2f} kg*m/s",
        )

    if op == "impulse":
        if "F" in p and "dt" in p:
            j_val = p["F"] * p["dt"]
            answer = (
                rf"J = F \Delta t = {p['F']:g} \cdot {p['dt']:g} "
                rf"\approx {j_val:.2f} \text{{ N}}\cdot\text{{s}}"
            )
        else:
            # J = Delta p. Same quantity, same units — N*s and kg*m/s are equal.
            j_val = p["m"] * (p["v2"] - p["v1"])
            answer = (
                rf"J = m \Delta v = {p['m']:g} \cdot "
                rf"({p['v2']:g} - {p['v1']:g}) \approx {j_val:.2f} \text{{ N}}\cdot\text{{s}}"
            )
        return PhysicsResult(answer=answer, answer_value=f"{j_val:.2f} N*s")

    if op == "final_velocity":
        m1, m2, v1, v2 = p["m1"], p["m2"], p["v1"], p["v2"]
        total = m1 + m2
        if total == 0:
            raise MathServiceError("colliding masses sum to zero")
        # The extractor refuses an unstated collision type, so this flag is
        # always something the user actually wrote.
        if p.get("elastic", 0.0) >= 0.5:
            u1 = ((m1 - m2) * v1 + 2 * m2 * v2) / total
            u2 = ((m2 - m1) * v2 + 2 * m1 * v1) / total
            answer = (
                r"\text{Elastic: } v_1' = \frac{(m_1-m_2)v_1 + 2 m_2 v_2}{m_1+m_2} "
                rf"\approx {u1:.2f} \text{{ m/s}}, \quad v_2' \approx {u2:.2f} \text{{ m/s}}"
            )
            answer_value = f"{u1:.2f} m/s and {u2:.2f} m/s"
        else:
            u1 = u2 = (m1 * v1 + m2 * v2) / total
            answer = (
                r"\text{Perfectly inelastic: } v = \frac{m_1 v_1 + m_2 v_2}{m_1 + m_2} = "
                rf"\frac{{{m1:g} \cdot {v1:g} + {m2:g} \cdot {v2:g}}}{{{total:g}}} "
                rf"\approx {u1:.2f} \text{{ m/s}}"
            )
            answer_value = f"{u1:.2f} m/s"
        return PhysicsResult(
            answer=answer,
            answer_value=answer_value,
            simulation_specs=[_collision_scene(m1, m2, v1, v2, u1, u2)],
        )

    raise MathServiceError(f"unsupported momentum op: {op}")


def _collision_scene(
    m1: float, m2: float, v1: float, v2: float, u1: float, u2: float
) -> SimulationBlockSpec:
    """Two bodies approaching, meeting, and leaving at their new speeds.

    The one thing a number genuinely cannot show. "1.00 m/s and 4.00 m/s" is
    the right answer and says nothing about which ball ends up ahead, whether
    either turns around, or that the pair keeps moving together when they
    stick — all of which the scene shows without a word.

    Contact is the midpoint of the clock, so the approach and the separation
    get equal screen time whatever the speeds. Radii come from the masses (as
    cube roots, since a ball's size goes with its volume), so the heavier body
    reads as the heavier one.
    """
    r1 = 0.30 * (m1 ** (1 / 3))
    r2 = 0.30 * (m2 ** (1 / 3))
    gap = r1 + r2

    # Long enough for the fastest phase to travel a few body-widths, so a slow
    # body still visibly moves and a fast one does not leave the box.
    fastest = max(abs(v1), abs(v2), abs(u1), abs(u2))
    half = (4 * gap / fastest) if fastest > 0 else 1.0

    n_half = 40
    dt = half / n_half
    path1: list[list[float]] = []
    path2: list[list[float]] = []
    for i in range(-n_half, n_half + 1):
        t = i * dt
        if t <= 0:
            # Contact at t = 0 puts the two surfaces together: centres a
            # radius either side of the origin.
            x1, x2 = -r1 + v1 * t, r2 + v2 * t
        else:
            x1, x2 = -r1 + u1 * t, r2 + u2 * t
        path1.append([round(x1, 4), 0.0])
        path2.append([round(x2, 4), 0.0])

    xs = [x for x, _ in path1 + path2]
    margin = gap
    lo, hi = min(xs) - margin, max(xs) + margin
    # A flat track: the bodies only move along x, so the box is wide and short
    # rather than square. Both axes still share one scale, so the balls stay
    # round.
    half_height = max((hi - lo) * 0.18, gap * 1.2)
    return SimulationBlockSpec(
        type="collision",
        title="Collision",
        bodies=[
            SimulationBody(path=path1, radius=r1, label=f"{m1:g} kg", role="primary"),
            SimulationBody(path=path2, radius=r2, label=f"{m2:g} kg", role="secondary"),
        ],
        x_min=lo,
        x_max=hi,
        y_min=-half_height,
        y_max=half_height,
        arrows=["velocity"],
    )


# ---------------------------------------------------------------------------
# Friction and inclined planes
#   N = m g cos(theta), f = mu N, a = g (sin(theta) - mu cos(theta))
# ---------------------------------------------------------------------------


def solve_friction(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "friction_force"
    g = p.get("g", 9.81)
    mu = p.get("mu", 0.0)
    theta = p.get("angle", 0.0)  # radians
    if g <= 0:
        raise MathServiceError("gravity must be positive")
    if mu < 0:
        raise MathServiceError("coefficient of friction cannot be negative")
    if not -math.pi / 2 < theta < math.pi / 2:
        raise MathServiceError("incline angle must be between -90 and 90 degrees")

    deg = math.degrees(theta)
    # Mass cancels out of the incline acceleration, so it is optional there and
    # only these two branches require it.
    if op in ("normal_force", "friction_force") and "m" not in p:
        raise MathServiceError(f"{op} needs a mass")
    normal = p.get("m", 0.0) * g * math.cos(theta)
    m = p.get("m", 0.0)

    if op == "normal_force":
        if theta == 0:
            answer = rf"N = m g = {m:g} \cdot {g:g} \approx {normal:.2f} \text{{ N}}"
        else:
            answer = (
                rf"N = m g \cos\theta = {m:g} \cdot {g:g} \cdot \cos({deg:g}^\circ) "
                rf"\approx {normal:.2f} \text{{ N}}"
            )
        return PhysicsResult(
            answer=answer,
            answer_value=f"{normal:.2f} N",
            simulation_specs=_incline_scene(deg, mu=mu),
        )

    if op == "friction_force":
        f_val = mu * normal
        answer = rf"f = \mu N = {mu:g} \cdot {normal:.2f} \approx {f_val:.2f} \text{{ N}}"
        return PhysicsResult(
            answer=answer,
            answer_value=f"{f_val:.2f} N",
            simulation_specs=_incline_scene(deg, mu=mu),
        )

    if op == "incline_acceleration":
        a_val = g * (math.sin(theta) - mu * math.cos(theta))
        if a_val <= 0:
            # tan(theta) <= mu: static friction holds it. Reporting a negative
            # acceleration would describe the block sliding *up* the slope on
            # its own, which is not what the equation means here.
            return PhysicsResult(
                answer=(
                    rf"\tan({deg:g}^\circ) \le \mu = {mu:g}, "
                    r"\text{so friction holds the block: } a = 0 \text{ m/s}^2"
                ),
                answer_value="0.00 m/s^2",
                # a = 0 is the answer, so the block stays put and the diagram
                # is the free body that explains why.
                simulation_specs=_incline_scene(deg, mu=mu),
            )
        answer = (
            r"a = g(\sin\theta - \mu\cos\theta) = "
            rf"{g:g}(\sin({deg:g}^\circ) - {mu:g}\cos({deg:g}^\circ)) "
            rf"\approx {a_val:.2f} \text{{ m/s}}^2"
        )
        return PhysicsResult(
            answer=answer,
            answer_value=f"{a_val:.2f} m/s^2",
            simulation_specs=_incline_scene(deg, mu=mu, accel=a_val),
        )

    if op == "friction_coefficient":
        mu_val = math.tan(theta)
        return PhysicsResult(
            answer=(rf"\mu = \tan(\theta) = \tan({deg:.1f}^\circ) \approx {mu_val:.2f}"),
            answer_value=f"{mu_val:.2f}",
            simulation_specs=_incline_scene(deg, mu=mu_val),
        )

    if op == "minimum_force":
        f_val = mu * m * g
        return PhysicsResult(
            answer=(
                rf"F_{{min}} = \mu m g = {mu:g} \cdot {m:g} \cdot {g:g} "
                rf"\approx {f_val:.2f} \text{{ N}}"
            ),
            answer_value=f"{f_val:.2f} N",
        )

    raise MathServiceError(f"unsupported friction op: {op}")


# The slope's own length is never stated, so it is a display choice and the
# scene is drawn at a fixed one. The same reasoning as the SHM curve's
# normalised amplitude: what the question is about is the *shape* of the
# motion — a block that starts slow and speeds up — and that shape is real
# whatever the slope measures. Inventing a number for the answer would be a
# different thing entirely.
_INCLINE_LENGTH = 6.0


def _incline_scene(
    deg: float, *, mu: float, accel: float | None = None
) -> list[SimulationBlockSpec]:
    """A block on a slope with its weight, normal and friction arrows.

    The ticket's third named scene, and the one that is mostly a *diagram*: a
    free-body picture is what an incline question wants, and for two of the
    three ops the block is not moving at all.

    A flat surface gets nothing. Weight down and normal up is a true picture
    and an empty one, and with no slope there is no friction direction to draw
    — the block is not going anywhere for friction to oppose.
    """
    if deg == 0:
        return []
    theta = math.radians(abs(deg))
    # Descending left to right, which fixes what "down the slope" means for
    # both the path and the arrows.
    down_x, down_y = math.cos(theta), -math.sin(theta)
    top_x, top_y = 0.0, _INCLINE_LENGTH * math.sin(theta)

    n_points = 60
    if accel is not None and accel > 0:
        # s = ½at², sampled uniformly in *time*, so the block visibly
        # accelerates rather than sliding at a constant rate. The duration is
        # the one that covers the drawn slope, so the block arrives at the
        # bottom exactly as the animation ends.
        duration = math.sqrt(2 * _INCLINE_LENGTH / accel)
        dt = duration / (n_points - 1)
        distances = [0.5 * accel * (i * dt) ** 2 for i in range(n_points)]
    else:
        # Held by friction, or an op with no acceleration to show: the block
        # stays where it is and the arrows are the whole picture.
        distances = [0.0] * n_points

    path = [[round(top_x + s * down_x, 4), round(top_y + s * down_y, 4)] for s in distances]
    arrows: list[str] = ["gravity", "normal"]
    if mu > 0:
        arrows.append("friction")

    margin = _INCLINE_LENGTH * 0.18
    return [
        SimulationBlockSpec(
            type="incline",
            title="Inclined Plane",
            bodies=[SimulationBody(path=path, radius=_INCLINE_LENGTH * 0.06)],
            x_min=-margin,
            x_max=_INCLINE_LENGTH * math.cos(theta) + margin,
            y_min=-margin,
            y_max=top_y + margin,
            arrows=arrows,  # type: ignore[arg-type]
            # The angle arrived here through radians, so 30 comes back as
            # 29.999999999999996 and would ship in the fence JSON that way.
            incline_deg=round(abs(deg), 4),
        )
    ]
