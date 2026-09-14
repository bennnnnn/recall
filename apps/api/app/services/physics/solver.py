"""Physics solvers — SymPy symbolic only (no SciPy).

Solves kinematics, projectile, force, and energy problems symbolically,
producing a LaTeX answer plus optional trajectory graph specs for the
SVG engine to render. All standard homework-level physics is solvable
with SymPy; SciPy is deferred until users hit ODE systems SymPy can't.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from sympy import Eq, Symbol, solve

from app.models.schemas.math import GraphBlockSpec, MathIntent
from app.services.math.solve import MathServiceError


@dataclass(frozen=True)
class PhysicsResult:
    """Result of a physics solve: a LaTeX answer + optional graph specs."""

    answer: str  # LaTeX, e.g. r"t = \sqrt{2 \cdot 20 / 9.81} \approx 2.02 \text{ s}"
    answer_value: str  # human-readable with units, e.g. "2.02 s"
    graph_specs: list[GraphBlockSpec] = field(default_factory=list)


def _latex_num(value: float, *, square: bool = False) -> str:
    """Format a number for LaTeX so ``-5^2`` is not read as ``-(5^2)``."""
    text = f"{value:g}"
    if value < 0:
        text = f"({text})"
    if square:
        return f"{text}^{{2}}"
    return text


_PARAM_SI_DIMENSIONS: dict[str, str] = {
    "h0": "meter",
    "h": "meter",
    "d": "meter",
    "v0": "meter / second",
    "v": "meter / second",
    "m": "kilogram",
    "F": "newton",
    "t": "second",
    "a": "meter / second ** 2",
    "g": "meter / second ** 2",
    "W": "joule",
    # Momentum / impulse / 1D collisions.
    "m1": "kilogram",
    "m2": "kilogram",
    "v1": "meter / second",
    "v2": "meter / second",
    "dt": "second",
    "r": "meter",
    "k": "newton / meter",
    "x": "meter",
    "V": "volt",
    "I": "ampere",
    "R": "ohm",
    "R1": "ohm",
    "R2": "ohm",
    "F1": "newton",
    "F2": "newton",
    "d1": "meter",
    # "mu" and "angle" are intentionally absent: mu is dimensionless and angle
    # is converted by _params_in_si before any unit check runs.
}

_UNIT_ALIASES = {
    "m/s2": "m/s**2",
    "m/s^2": "m/s**2",
    "deg": "deg",
    "degrees": "deg",
    "°": "deg",
    "miles per hour": "mph",
    "miles": "mile",
    "ohms": "ohm",
    "volts": "volt",
    "amps": "ampere",
    "amperes": "ampere",
}


def _to_si(value: float, unit: str, *, expected_key: str | None = None) -> float:
    """Convert a value with a unit string to its SI base using Pint.

    Returns the value unchanged if the unit is empty (assumed already SI).
    Raises when ``expected_key`` has a known dimension and the unit does not match.
    """
    if not unit:
        return value
    from app.services.math.school import _get_unit_registry

    ureg = _get_unit_registry()
    alias = _UNIT_ALIASES.get(unit.lower(), unit)
    try:
        quantity = value * ureg(alias)
        dim_spec = _PARAM_SI_DIMENSIONS.get(expected_key) if expected_key else None
        if dim_spec is not None and quantity.dimensionality != ureg(dim_spec).dimensionality:
            raise MathServiceError(
                f"unit {unit} does not match expected dimension for {expected_key}"
            )
        base = quantity.to_base_units()
        return float(base.magnitude)
    except MathServiceError:
        raise
    except Exception as exc:
        raise MathServiceError(f"unsupported unit: {unit}") from exc


def _params_in_si(intent: MathIntent) -> dict[str, float]:
    """Convert all physics_params to SI base units using Pint."""
    params = intent.physics_params or {}
    units = intent.physics_units or {}
    out: dict[str, float] = {}
    for key, val in params.items():
        unit = units.get(key, "")
        if key == "angle":
            lower_unit = unit.lower()
            if lower_unit in ("rad", "radian", "radians"):
                out[key] = val
            else:
                out[key] = math.radians(val) if lower_unit in ("deg", "degrees", "°", "") else val
        else:
            out[key] = _to_si(val, unit, expected_key=key)
    return out


# ---------------------------------------------------------------------------
# Kinematics: 1D motion under gravity
#   h(t) = h0 + v0*t - 0.5*g*t^2
#   v(t) = v0 - g*t
# ---------------------------------------------------------------------------


def solve_kinematics(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    g = p.get("g", 9.81)
    h0 = p.get("h0", 0.0)
    v0 = p.get("v0", 0.0)
    op = intent.physics_op or "time_to_ground"
    if g <= 0:
        raise MathServiceError("gravity must be positive")

    t = Symbol("t", positive=True, real=True)
    h_sym = h0 + v0 * t - 0.5 * g * t**2

    def _time_to_ground() -> float | None:
        solutions = solve(Eq(h_sym, 0), t)
        valid = [s for s in solutions if s.is_real and s > 0] if solutions else []
        if not valid:
            return None
        return float(valid[0])

    # Past impact, h(t) is negative and v(t) is still "in air" — not a fact.
    if op in ("position", "velocity", "speed"):
        t_asked = p.get("t")
        t_land = _time_to_ground()
        if t_asked is not None and t_land is not None and float(t_asked) > t_land:
            raise MathServiceError("already on the ground")

    if op == "time_to_ground":
        # Solve h(t) = 0 for t > 0.
        landed = _time_to_ground()
        if landed is None:
            raise MathServiceError("no positive real time to ground")
        t_val = landed
        v0_sq = _latex_num(v0, square=True)
        answer_latex = (
            r"t = \frac{v_0 + \sqrt{v_0^2 + 2 g h_0}}{g} = "
            rf"\frac{{{_latex_num(v0)} + \sqrt{{{v0_sq} + 2 \cdot {g:g} \cdot {h0:g}}}}}"
            rf"{{{g:g}}} "
            rf"\approx {t_val:.2f} \text{{ s}}"
        )
        answer_value = f"{t_val:.2f} s"
    elif op in ("velocity", "speed"):
        # Need a time — look for a time param, else use time_to_ground.
        t_param = p.get("t")
        if t_param is None:
            landed = _time_to_ground()
            if landed is None:
                raise MathServiceError("no positive real time to ground")
            t_param = landed
        t_val = float(t_param)
        v_val = float(v0 - g * t_val)
        if op == "speed":
            v_val = abs(v_val)
            answer_latex = rf"v = \lvert v_0 - g \cdot t\rvert \approx {v_val:.2f} \text{{ m/s}}"
        else:
            answer_latex = rf"v = v_0 - g \cdot t \approx {v_val:.2f} \text{{ m/s}}"
        answer_value = f"{v_val:.2f} m/s"
    elif op == "position":
        t_param = p.get("t")
        if t_param is None:
            raise MathServiceError("position requires a time t")
        t_val = float(t_param)
        h_val = float(h0 + v0 * t_val - 0.5 * g * t_val**2)
        answer_latex = rf"h = h_0 + v_0 t - \frac{{1}}{{2}} g t^2 \approx {h_val:.2f} \text{{ m}}"
        answer_value = f"{h_val:.2f} m"
    elif op == "acceleration":
        # Constant g for free-fall templates only. The extractor returns
        # None unless a gravity-motion cue is present — do not use this
        # for two-point velocity acceleration.
        answer_latex = rf"a = -g = {-g:g} \text{{ m/s}}^2"
        answer_value = f"{-g:g} m/s^2"
        return PhysicsResult(answer=answer_latex, answer_value=answer_value)
    else:
        raise MathServiceError(f"unsupported kinematics op: {op}")

    n_points = 100

    # A "how fast after 1 s" ask gets v(t), not h(t). Plotting height against a
    # question about speed answers a different question than the one asked, and
    # `velocity_vs_time` has been declared on both sides of the wire — and
    # emitted by nothing — since the type was introduced.
    if op in ("velocity", "speed"):
        # No h0/v0 guard here: v(t) = v0 - g*t is a real line even for a drop
        # from an unstated height, which is exactly the case h(t) cannot plot.
        # Only a zero-length window is degenerate.
        if t_val <= 0:
            return PhysicsResult(answer=answer_latex, answer_value=answer_value)
        t_max = t_val * 1.05
        dt = t_max / (n_points - 1)
        v_points: list[list[float]] = []
        for i in range(n_points):
            ti = i * dt
            vi = v0 - g * ti
            if op == "speed":
                vi = abs(vi)
            v_points.append([round(ti, 4), round(float(vi), 4)])
        is_speed = op == "speed"
        return PhysicsResult(
            answer=answer_latex,
            answer_value=answer_value,
            graph_specs=[
                GraphBlockSpec(
                    type="trajectory",
                    expr=(f"v(t) = |{v0:g} - {g:g}*t|" if is_speed else f"v(t) = {v0:g} - {g:g}*t"),
                    variable="t",
                    x_min=0.0,
                    x_max=t_max,
                    points=v_points,
                    title="Speed vs. Time" if is_speed else "Velocity vs. Time",
                    x_label="Time (s)",
                    y_label="Speed (m/s)" if is_speed else "Velocity (m/s)",
                    trajectory_type="velocity_vs_time",
                )
            ],
        )

    # Build trajectory graph: height vs time, from t=0 to t=t_val (ground).
    # Skip it when neither a height nor a launch speed was given: h(t) would
    # be entirely below ground and clamp to a flat line at zero, which reads
    # as "it never moved". The answer is still exact.
    if h0 <= 0 and v0 == 0:
        return PhysicsResult(answer=answer_latex, answer_value=answer_value)

    t_max = t_val * 1.05  # small pad so the curve doesn't end exactly at ground
    dt = t_max / (n_points - 1)
    points: list[list[float]] = []
    for i in range(n_points):
        ti = i * dt
        hi = h0 + v0 * ti - 0.5 * g * ti**2
        # Clamp negative heights (after ground) to 0 for a clean plot.
        if hi < 0:
            hi = 0.0
        points.append([round(ti, 4), round(float(hi), 4)])

    graph_spec = GraphBlockSpec(
        type="trajectory",
        expr=f"h(t) = {h0:g} + {v0:g}*t - 0.5*{g:g}*t^2",
        variable="t",
        x_min=0.0,
        x_max=t_max,
        points=points,
        title="Height vs. Time",
        # Trajectory-specific labels (P6).
        x_label="Time (s)",
        y_label="Height (m)",
        trajectory_type="position_vs_time",
    )
    return PhysicsResult(
        answer=answer_latex,
        answer_value=answer_value,
        graph_specs=[graph_spec],
    )


# ---------------------------------------------------------------------------
# Projectile: 2D motion at an angle
#   x(t) = v0*cos(θ)*t
#   y(t) = v0*sin(θ)*t - 0.5*g*t^2
#   Range R = v0^2*sin(2θ)/g
#   Max height H = v0^2*sin^2(θ)/(2g)
# ---------------------------------------------------------------------------


def solve_projectile(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    g = p.get("g", 9.81)
    v0 = p["v0"]
    theta = p["angle"]  # radians (converted by _params_in_si)
    op = intent.physics_op or "range"
    h0 = p.get("h0", 0.0)

    if h0 > 0:
        # y = h0 + v0 sinθ t - ½ g t² = 0 → ½ g t² - v0 sinθ t - h0 = 0
        a = 0.5 * g
        b = -v0 * math.sin(theta)
        c = -h0
        disc = b * b - 4 * a * c
        if disc < 0:
            raise MathServiceError("projectile has no positive flight time")
        t_flight = (-b + math.sqrt(disc)) / (2 * a)
    else:
        t_flight = 2 * v0 * math.sin(theta) / g
    if t_flight <= 0:
        raise MathServiceError("projectile has no positive flight time")

    if op == "range":
        if h0 > 0:
            r_val = v0 * math.cos(theta) * t_flight
        else:
            r_val = v0**2 * math.sin(2 * theta) / g
        deg = math.degrees(theta)
        v0_sq = _latex_num(v0, square=True)
        answer_latex = (
            rf"R = \frac{{v_0^2 \sin(2\theta)}}{{g}} = "
            rf"\frac{{{v0_sq} \cdot \sin({deg:.1f}^\circ \cdot 2)}}{{{g:g}}} "
            rf"\approx {r_val:.2f} \text{{ m}}"
            if h0 <= 0
            else rf"R = v_0 \cos(\theta)\, t \approx {r_val:.2f} \text{{ m}}"
        )
        answer_value = f"{r_val:.2f} m"
    elif op == "max_height":
        h_val = h0 + v0**2 * math.sin(theta) ** 2 / (2 * g)
        answer_latex = (
            rf"H = h_0 + \frac{{v_0^2 \sin^2(\theta)}}{{2g}} = "
            rf"{h_val:.2f} \text{{ m}}"
        )
        answer_value = f"{h_val:.2f} m"
    else:
        raise MathServiceError(f"unsupported projectile op: {op}")

    # Build trajectory graph: parametric (x(t), y(t)) from t=0 to t=t_flight.
    n_points = 100
    dt = t_flight / (n_points - 1)
    points: list[list[float]] = []
    for i in range(n_points):
        ti = i * dt
        xi = v0 * math.cos(theta) * ti
        yi = h0 + v0 * math.sin(theta) * ti - 0.5 * g * ti**2
        if yi < 0:
            yi = 0.0
        points.append([round(xi, 4), round(float(yi), 4)])

    graph_spec = GraphBlockSpec(
        type="trajectory",
        expr=f"y(x) = x*tan({math.degrees(theta):.1f} deg) - g*x^2/(2*v0^2*cos^2(theta))",
        variable="x",
        x_min=0.0,
        x_max=points[-1][0] * 1.05,
        points=points,
        title="Projectile Trajectory",
        x_label="Distance (m)",
        y_label="Height (m)",
        trajectory_type="parametric",
    )
    return PhysicsResult(
        answer=answer_latex,
        answer_value=answer_value,
        graph_specs=[graph_spec],
    )


# ---------------------------------------------------------------------------
# Force: F = m a
# ---------------------------------------------------------------------------


def solve_force(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
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
    return PhysicsResult(answer=answer_latex, answer_value=answer_value)


# ---------------------------------------------------------------------------
# Energy: KE = ½ m v², PE = m g h, W = F d, P = F v or W / t
# ---------------------------------------------------------------------------


def solve_energy(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    g = p.get("g", 9.81)
    op = intent.physics_op or "kinetic_energy"

    if op == "kinetic_energy":
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
    return PhysicsResult(answer=answer_latex, answer_value=answer_value)


# ---------------------------------------------------------------------------
# Momentum: p = m v, impulse J = F dt (or m dv), 1D collisions
#   inelastic: v = (m1 v1 + m2 v2) / (m1 + m2)
#   elastic:   v1' = ((m1-m2) v1 + 2 m2 v2) / (m1+m2), v2' symmetric
# ---------------------------------------------------------------------------


def solve_momentum(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "momentum"

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
            u = (m1 * v1 + m2 * v2) / total
            answer = (
                r"\text{Perfectly inelastic: } v = \frac{m_1 v_1 + m_2 v_2}{m_1 + m_2} = "
                rf"\frac{{{m1:g} \cdot {v1:g} + {m2:g} \cdot {v2:g}}}{{{total:g}}} "
                rf"\approx {u:.2f} \text{{ m/s}}"
            )
            answer_value = f"{u:.2f} m/s"
        return PhysicsResult(answer=answer, answer_value=answer_value)

    raise MathServiceError(f"unsupported momentum op: {op}")


# ---------------------------------------------------------------------------
# Friction and inclined planes
#   N = m g cos(theta), f = mu N, a = g (sin(theta) - mu cos(theta))
# ---------------------------------------------------------------------------


def solve_friction(intent: MathIntent) -> PhysicsResult:
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
        return PhysicsResult(answer=answer, answer_value=f"{normal:.2f} N")

    if op == "friction_force":
        f_val = mu * normal
        answer = rf"f = \mu N = {mu:g} \cdot {normal:.2f} \approx {f_val:.2f} \text{{ N}}"
        return PhysicsResult(answer=answer, answer_value=f"{f_val:.2f} N")

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
            )
        answer = (
            r"a = g(\sin\theta - \mu\cos\theta) = "
            rf"{g:g}(\sin({deg:g}^\circ) - {mu:g}\cos({deg:g}^\circ)) "
            rf"\approx {a_val:.2f} \text{{ m/s}}^2"
        )
        return PhysicsResult(answer=answer, answer_value=f"{a_val:.2f} m/s^2")

    raise MathServiceError(f"unsupported friction op: {op}")


# ---------------------------------------------------------------------------
# Circular motion: a_c = v^2/r, F_c = m v^2/r, T = 2 pi r / v
# ---------------------------------------------------------------------------


def solve_circular(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "centripetal_acceleration"
    r = p["r"]
    v = p["v"]
    if r <= 0:
        raise MathServiceError("radius must be positive")

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
        )

    a_c = v * v / r
    if op == "centripetal_acceleration":
        return PhysicsResult(
            answer=(
                rf"a_c = \frac{{v^2}}{{r}} = \frac{{{_latex_num(v, square=True)}}}{{{r:g}}} "
                rf"\approx {a_c:.2f} \text{{ m/s}}^2"
            ),
            answer_value=f"{a_c:.2f} m/s^2",
        )

    if op == "centripetal_force":
        if "m" not in p:
            raise MathServiceError("centripetal force needs a mass")
        f_val = p["m"] * a_c
        return PhysicsResult(
            answer=(
                rf"F_c = \frac{{m v^2}}{{r}} = \frac{{{p['m']:g} \cdot "
                rf"{_latex_num(v, square=True)}}}{{{r:g}}} \approx {f_val:.2f} \text{{ N}}"
            ),
            answer_value=f"{f_val:.2f} N",
        )

    raise MathServiceError(f"unsupported circular op: {op}")


# ---------------------------------------------------------------------------
# Springs: F = k x, U = 1/2 k x^2, T = 2 pi sqrt(m/k)
# ---------------------------------------------------------------------------


def solve_spring(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "spring_force"
    k = p["k"]
    if k <= 0:
        raise MathServiceError("spring constant must be positive")

    if op == "spring_force":
        x = p["x"]
        f_val = k * abs(x)
        return PhysicsResult(
            answer=(rf"F = kx = {k:g} \cdot {abs(x):g} \approx {f_val:.2f} \text{{ N}}"),
            answer_value=f"{f_val:.2f} N",
        )

    if op == "spring_energy":
        x = p["x"]
        u_val = 0.5 * k * x * x
        return PhysicsResult(
            answer=(
                rf"U = \tfrac{{1}}{{2}} k x^2 = 0.5 \cdot {k:g} \cdot "
                rf"{_latex_num(x, square=True)} \approx {u_val:.2f} \text{{ J}}"
            ),
            answer_value=f"{u_val:.2f} J",
        )

    if op == "shm_period":
        m = p["m"]
        if m <= 0:
            raise MathServiceError("mass must be positive")
        t_period = 2 * math.pi * math.sqrt(m / k)
        answer = (
            rf"T = 2\pi\sqrt{{\frac{{m}}{{k}}}} = 2\pi\sqrt{{\frac{{{m:g}}}{{{k:g}}}}} "
            rf"\approx {t_period:.2f} \text{{ s}}"
        )

        # The oscillation is the thing worth seeing, so hand P3's player a
        # curve. Amplitude only scales the y-axis — the shape and the period
        # are what the question is about — so when none is given the plot is
        # normalised rather than invented.
        amplitude = p.get("x")
        n_points = 100
        span = 2 * t_period
        dt = span / (n_points - 1)
        a_plot = abs(amplitude) if amplitude else 1.0
        points = [
            [round(i * dt, 4), round(a_plot * math.cos(2 * math.pi * (i * dt) / t_period), 4)]
            for i in range(n_points)
        ]
        spec = GraphBlockSpec(
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
        return PhysicsResult(answer=answer, answer_value=f"{t_period:.2f} s", graph_specs=[spec])

    raise MathServiceError(f"unsupported spring op: {op}")


# ---------------------------------------------------------------------------
# Circuits: V = I R, P = V I, series/parallel resistance
# ---------------------------------------------------------------------------


def solve_circuit(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "current"

    if op in ("series_resistance", "parallel_resistance"):
        r1, r2 = p["R1"], p["R2"]
        if r1 <= 0 or r2 <= 0:
            raise MathServiceError("resistances must be positive")
        if op == "series_resistance":
            total = r1 + r2
            answer = rf"R = R_1 + R_2 = {r1:g} + {r2:g} \approx {total:.2f} \,\Omega"
        else:
            total = 1 / (1 / r1 + 1 / r2)
            answer = (
                r"\frac{1}{R} = \frac{1}{R_1} + \frac{1}{R_2} \Rightarrow R = "
                rf"\frac{{{r1:g} \cdot {r2:g}}}{{{r1:g} + {r2:g}}} \approx {total:.2f} \,\Omega"
            )
        return PhysicsResult(answer=answer, answer_value=f"{total:.2f} ohm")

    if op == "electrical_power":
        if "V" in p and "I" in p:
            val = p["V"] * p["I"]
            answer = rf"P = VI = {p['V']:g} \cdot {p['I']:g} \approx {val:.2f} \text{{ W}}"
        elif "I" in p and "R" in p:
            val = p["I"] ** 2 * p["R"]
            answer = (
                rf"P = I^2 R = {_latex_num(p['I'], square=True)} \cdot {p['R']:g} "
                rf"\approx {val:.2f} \text{{ W}}"
            )
        elif "V" in p and "R" in p:
            if p["R"] == 0:
                raise MathServiceError("resistance must be nonzero")
            val = p["V"] ** 2 / p["R"]
            answer = (
                rf"P = \frac{{V^2}}{{R}} = \frac{{{_latex_num(p['V'], square=True)}}}"
                rf"{{{p['R']:g}}} \approx {val:.2f} \text{{ W}}"
            )
        else:
            raise MathServiceError("electrical power needs two of V, I, R")
        return PhysicsResult(answer=answer, answer_value=f"{val:.2f} W")

    if op == "current":
        if p["R"] == 0:
            raise MathServiceError("resistance must be nonzero")
        val = p["V"] / p["R"]
        return PhysicsResult(
            answer=(
                rf"I = \frac{{V}}{{R}} = \frac{{{p['V']:g}}}{{{p['R']:g}}} "
                rf"\approx {val:.2f} \text{{ A}}"
            ),
            answer_value=f"{val:.2f} A",
        )

    if op == "voltage":
        val = p["I"] * p["R"]
        return PhysicsResult(
            answer=rf"V = IR = {p['I']:g} \cdot {p['R']:g} \approx {val:.2f} \text{{ V}}",
            answer_value=f"{val:.2f} V",
        )

    if op == "resistance":
        if p["I"] == 0:
            raise MathServiceError("current must be nonzero")
        val = p["V"] / p["I"]
        return PhysicsResult(
            answer=(
                rf"R = \frac{{V}}{{I}} = \frac{{{p['V']:g}}}{{{p['I']:g}}} "
                rf"\approx {val:.2f} \,\Omega"
            ),
            answer_value=f"{val:.2f} ohm",
        )

    raise MathServiceError(f"unsupported circuit op: {op}")


# ---------------------------------------------------------------------------
# Torque: tau = F d sin(theta); balance F1 d1 = F2 d2
# ---------------------------------------------------------------------------


def solve_torque(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "torque"

    if op == "moment_balance":
        f1, d1, f2 = p["F1"], p["d1"], p["F2"]
        if f2 == 0:
            raise MathServiceError("balancing force must be nonzero")
        d2 = f1 * d1 / f2
        return PhysicsResult(
            answer=(
                r"F_1 d_1 = F_2 d_2 \Rightarrow d_2 = \frac{F_1 d_1}{F_2} = "
                rf"\frac{{{f1:g} \cdot {d1:g}}}{{{f2:g}}} \approx {d2:.2f} \text{{ m}}"
            ),
            answer_value=f"{d2:.2f} m",
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
        else:
            tau = f * d * math.sin(theta)
            deg = math.degrees(theta)
            answer = (
                rf"\tau = F d \sin\theta = {f:g} \cdot {d:g} \cdot \sin({deg:g}^\circ) "
                rf"\approx {tau:.2f} \text{{ N}}\cdot\text{{m}}"
            )
        return PhysicsResult(answer=answer, answer_value=f"{tau:.2f} N*m")

    raise MathServiceError(f"unsupported torque op: {op}")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def solve_physics(intent: MathIntent) -> PhysicsResult:
    """Dispatch to the right solver by intent kind."""
    if intent.kind == "kinematics":
        return solve_kinematics(intent)
    if intent.kind == "projectile":
        return solve_projectile(intent)
    if intent.kind == "force":
        return solve_force(intent)
    if intent.kind == "energy":
        return solve_energy(intent)
    if intent.kind == "momentum":
        return solve_momentum(intent)
    if intent.kind == "friction":
        return solve_friction(intent)
    if intent.kind == "circular":
        return solve_circular(intent)
    if intent.kind == "spring":
        return solve_spring(intent)
    if intent.kind == "circuit":
        return solve_circuit(intent)
    if intent.kind == "torque":
        return solve_torque(intent)
    raise MathServiceError(f"not a physics kind: {intent.kind}")
