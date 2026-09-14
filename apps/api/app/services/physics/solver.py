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
}

_UNIT_ALIASES = {
    "m/s2": "m/s**2",
    "m/s^2": "m/s**2",
    "deg": "deg",
    "degrees": "deg",
    "°": "deg",
    "miles per hour": "mph",
    "miles": "mile",
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
    raise MathServiceError(f"not a physics kind: {intent.kind}")
