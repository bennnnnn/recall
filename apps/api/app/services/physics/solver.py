"""Physics solvers — SymPy symbolic only (no SciPy).

Solves kinematics, projectile, force, and energy problems symbolically,
producing a LaTeX answer plus optional trajectory graph specs for the
SVG engine to render. All standard homework-level physics is solvable
with SymPy; SciPy is deferred until users hit ODE systems SymPy can't.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from sympy import Eq, Symbol, solve

from app.models.schemas.math import (
    GraphBlockSpec,
    MathIntent,
    SimulationBlockSpec,
    SimulationBody,
    SimulationVector,
)
from app.services.math.solve import MathServiceError


@dataclass(frozen=True)
class PhysicsResult:
    """Result of a physics solve: a LaTeX answer + optional graph/scene specs."""

    answer: str  # LaTeX, e.g. r"t = \sqrt{2 \cdot 20 / 9.81} \approx 2.02 \text{ s}"
    answer_value: str  # human-readable with units, e.g. "2.02 s"
    graph_specs: list[GraphBlockSpec] = field(default_factory=list)
    # A scene of moving bodies, where the graph is a plot of one. A solve may
    # emit both: the projectile's parabola *and* the ball flying along it.
    simulation_specs: list[SimulationBlockSpec] = field(default_factory=list)


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
    "R3": "ohm",
    "R4": "ohm",
    # Round 3 circuits. Single letters are taken (V is volt, I is ampere, R is
    # ohm), so anything new here is spelled out.
    "Q": "coulomb",
    "power": "watt",
    "E_emf": "volt",
    "r_int": "ohm",
    # Round 3 SHM. "period" and "omega" spelled out: T is tesla to Pint and a
    # temperature to thermodynamics, and a bare w is not a unit at all.
    "period": "second",
    "omega": "radian / second",
    # Round 3 waves. Every key here is spelled out: Pint reads a bare "t" as a
    # tonne, "c" as the speed of light and "pa" as a *petayear*, so a param
    # without an entry in this table is not merely unvalidated - it can convert
    # into the wrong dimension entirely and answer confidently.
    "freq": "hertz",
    "wavelength": "meter",
    "v_wave": "meter / second",
    "v_src": "meter / second",
    "v_sound": "meter / second",
    # Round 3 optics. `u` is SUVAT's initial velocity and `f` is not a param,
    # so the conventional letters are spelled out here too.
    "focal": "meter",
    "d_obj": "meter",
    "d_img": "meter",
    "h_obj": "meter",
    "h_img": "meter",
    # Round 3 thermal. "temp" is absolute and "delta_temp" is an interval -
    # the same number in kelvin and celsius, which "temp" is not.
    "temp": "kelvin",
    "delta_temp": "kelvin",
    "c_heat": "joule / kilogram / kelvin",
    "heat": "joule",
    "W_out": "joule",
    "Q_in": "joule",
    "pres": "pascal",
    "volume": "meter ** 3",
    "moles": "mole",
    # Round 3 gravitation. "M" beside "m" is case-only, but it is how the
    # formula is written and the pair always appears together.
    "M": "kilogram",
    "radius_body": "meter",
    "altitude": "meter",
    # Round 3 fluids.
    "rho": "kilogram / meter ** 3",
    "depth": "meter",
    "area": "meter ** 2",
    "A1": "meter ** 2",
    "A2": "meter ** 2",
    # Round 3 rotation. "I" is already the ampere.
    "inertia": "kilogram * meter ** 2",
    "theta": "radian",
    # Round 3 magnetism. "B" is free; "T" is not, being the tesla to Pint and a
    # temperature to thermodynamics.
    "b_field": "tesla",
    "wire_L": "meter",
    "flux": "weber",
    # Round 3 materials.
    "sigma": "pascal",
    "E_mod": "pascal",
    "L0": "meter",
    "dL": "meter",
    "F1": "newton",
    "F2": "newton",
    "d1": "meter",
    # SUVAT initial velocity. "v" and "a" and "t" and "d" are already above.
    "u": "meter / second",
    # Pendulum length.
    "L": "meter",
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
    # Pint is case-sensitive and unforgiving about the symbols people type:
    # bare "pa" is a petayear, "t" a tonne, "c" the speed of light, and "w",
    # "n", "j", "hz" are not units at all. Every extractor regex here is
    # IGNORECASE, so the lowercase spellings do arrive.
    "w": "watt",
    "watts": "watt",
    "kw": "kilowatt",
    "kilowatts": "kilowatt",
    "c": "coulomb",
    "coulombs": "coulomb",
    "f": "farad",
    "farads": "farad",
    "j": "joule",
    "joules": "joule",
    "rad/s": "radian / second",
    "rads/s": "radian / second",
    "radians/s": "radian / second",
    "rad/sec": "radian / second",
    "hz": "hertz",
    "khz": "kilohertz",
    "mhz": "megahertz",
    "pa": "pascal",
    "kpa": "kilopascal",
    "mpa": "megapascal",
    "k": "kelvin",
    "kelvins": "kelvin",
    "\u00b0c": "degC",
    "celsius": "degC",
    "j/kg/k": "joule / kilogram / kelvin",
    "j/(kg k)": "joule / kilogram / kelvin",
    "j/kgk": "joule / kilogram / kelvin",
    "m^3": "m**3",
    "m3": "m**3",
    "cm^3": "cm**3",
    "cm3": "cm**3",
    "litres": "liter",
    "litre": "liter",
    "liters": "liter",
    "moles": "mole",
    "m^2": "m**2",
    "m2": "m**2",
    "cm^2": "cm**2",
    "cm2": "cm**2",
    "mm^2": "mm**2",
    "kg/m^3": "kg/m**3",
    "kg/m3": "kg/m**3",
    "g/cm^3": "g/cm**3",
    "g/cm3": "g/cm**3",
    "kg*m^2": "kg * m**2",
    "kg m^2": "kg * m**2",
    "kgm^2": "kg * m**2",
    "rad": "radian",
    "radians": "radian",
    "t": "tesla",
    "tesla": "tesla",
    "teslas": "tesla",
    "mt": "millitesla",
    "wb": "weber",
    "weber": "weber",
    "webers": "weber",
    "n": "newton",
    "newtons": "newton",
    "gpa": "gigapascal",
}


# R1..R4 name a resistor network's members. Single-digit, so plain `sorted`
# orders them correctly.
_RESISTOR_KEY_RE = re.compile(r"R[1-9]")


# Units whose zero is not zero. These must be constructed as a Quantity rather
# than multiplied, and a *difference* in them is not the same as a value.
_OFFSET_UNITS = frozenset({"degC", "degF", "celsius", "fahrenheit"})

# CODATA, read from the unit registry rather than typed: a transposed digit in
# a hand-written constant is a wrong answer nothing else would catch.
_GAS_CONSTANT = 8.314462618153241
_BIG_G = 6.67430e-11
_PLANCK_H = 6.62607015e-34
_SPEED_OF_LIGHT = 299792458.0
_ELEMENTARY_CHARGE = 1.602176634e-19


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
        if alias in _OFFSET_UNITS:
            # Celsius is an offset unit, not a scale factor: `value * ureg(
            # "degC")` raises OffsetUnitCalculusError rather than converting.
            quantity = ureg.Quantity(value, alias)
        else:
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
        # `startswith`, not `==`: Snell's law carries `angle` and `angle2`, and
        # an angle that skipped this branch would reach `_to_si` and convert
        # only because Pint's `degree` happens to base-convert to radians.
        if key.startswith("angle"):
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
# SUVAT: motion under any constant acceleration
#   v = u + at        s = ut + ½at²
#   v² = u² + 2as     s = ½(u + v)t
#
# The four equations each omit one variable, so the givens choose the equation
# rather than the wording choosing it — the same "read the question from its
# givens" shape P8 used for Ohm's law, and the reason four sets of phrasing
# rules were not needed.
# ---------------------------------------------------------------------------


def _suvat_velocity(p: dict[str, float]) -> tuple[float, str]:
    u, a, t, d = p.get("u"), p.get("a"), p.get("t"), p.get("d")
    if u is not None and a is not None and t is not None:
        return u + a * t, rf"v = u + at = {u:g} + {_latex_num(a)} \cdot {t:g}"
    if u is not None and a is not None and d is not None:
        square = u * u + 2 * a * d
        if square < 0:
            raise MathServiceError("no real final velocity: the body stops before that distance")
        return (
            math.sqrt(square),
            rf"v = \sqrt{{u^2 + 2as}} = \sqrt{{{_latex_num(u, square=True)} + "
            rf"2 \cdot {_latex_num(a)} \cdot {d:g}}}",
        )
    if u is not None and d is not None and t is not None:
        if t == 0:
            raise MathServiceError("time must be non-zero")
        return (
            2 * d / t - u,
            rf"s = \tfrac{{1}}{{2}}(u + v)t \Rightarrow v = \frac{{2s}}{{t}} - u = "
            rf"\frac{{2 \cdot {d:g}}}{{{t:g}}} - {u:g}",
        )
    raise MathServiceError("not enough givens for a final velocity")


def _suvat_distance(p: dict[str, float]) -> tuple[float, str]:
    u, v, a, t = p.get("u"), p.get("v"), p.get("a"), p.get("t")
    if u is not None and a is not None and t is not None:
        return (
            u * t + 0.5 * a * t * t,
            rf"s = ut + \tfrac{{1}}{{2}}at^2 = {u:g} \cdot {t:g} + 0.5 \cdot "
            rf"{_latex_num(a)} \cdot {_latex_num(t, square=True)}",
        )
    if u is not None and v is not None and a is not None:
        if a == 0:
            raise MathServiceError("acceleration must be non-zero to find a distance this way")
        return (
            (v * v - u * u) / (2 * a),
            rf"v^2 = u^2 + 2as \Rightarrow s = \frac{{v^2 - u^2}}{{2a}} = "
            rf"\frac{{{_latex_num(v, square=True)} - {_latex_num(u, square=True)}}}"
            rf"{{2 \cdot {_latex_num(a)}}}",
        )
    if u is not None and v is not None and t is not None:
        return (
            0.5 * (u + v) * t,
            rf"s = \tfrac{{1}}{{2}}(u + v)t = 0.5 \cdot ({u:g} + {v:g}) \cdot {t:g}",
        )
    raise MathServiceError("not enough givens for a distance")


def _suvat_time(p: dict[str, float]) -> tuple[float, str]:
    u, v, a, d = p.get("u"), p.get("v"), p.get("a"), p.get("d")
    if u is not None and v is not None and a is not None:
        if a == 0:
            raise MathServiceError("acceleration must be non-zero to find a time this way")
        return (
            (v - u) / a,
            rf"v = u + at \Rightarrow t = \frac{{v - u}}{{a}} = "
            rf"\frac{{{v:g} - {u:g}}}{{{_latex_num(a)}}}",
        )
    if u is not None and a is not None and d is not None:
        # ½at² + ut - s = 0. SymPy rather than the quadratic formula by hand,
        # and the earliest non-negative root is the physical one.
        t_sym = Symbol("t", real=True)
        roots = solve(Eq(0.5 * a * t_sym**2 + u * t_sym, d), t_sym)
        candidates = sorted(float(r) for r in roots if r.is_real and float(r) >= 0)
        if not candidates:
            raise MathServiceError("the body never reaches that distance")
        return (
            candidates[0],
            rf"s = ut + \tfrac{{1}}{{2}}at^2 \Rightarrow 0.5 \cdot {_latex_num(a)} t^2 + "
            rf"{u:g}t = {d:g}",
        )
    if u is not None and v is not None and d is not None:
        if u + v == 0:
            raise MathServiceError("average velocity is zero, so no time follows")
        return (
            2 * d / (u + v),
            rf"s = \tfrac{{1}}{{2}}(u + v)t \Rightarrow t = \frac{{2s}}{{u + v}} = "
            rf"\frac{{2 \cdot {d:g}}}{{{u:g} + {v:g}}}",
        )
    raise MathServiceError("not enough givens for a time")


def _suvat_acceleration(p: dict[str, float]) -> tuple[float, str]:
    u, v, t, d = p.get("u"), p.get("v"), p.get("t"), p.get("d")
    if u is not None and v is not None and t is not None:
        if t == 0:
            raise MathServiceError("time must be non-zero")
        return (
            (v - u) / t,
            rf"v = u + at \Rightarrow a = \frac{{v - u}}{{t}} = "
            rf"\frac{{{v:g} - {u:g}}}{{{t:g}}}",
        )
    if u is not None and v is not None and d is not None:
        if d == 0:
            raise MathServiceError("distance must be non-zero")
        return (
            (v * v - u * u) / (2 * d),
            rf"v^2 = u^2 + 2as \Rightarrow a = \frac{{v^2 - u^2}}{{2s}} = "
            rf"\frac{{{_latex_num(v, square=True)} - {_latex_num(u, square=True)}}}"
            rf"{{2 \cdot {d:g}}}",
        )
    if u is not None and t is not None and d is not None:
        if t == 0:
            raise MathServiceError("time must be non-zero")
        return (
            2 * (d - u * t) / (t * t),
            rf"s = ut + \tfrac{{1}}{{2}}at^2 \Rightarrow a = \frac{{2(s - ut)}}{{t^2}} = "
            rf"\frac{{2({d:g} - {u:g} \cdot {t:g})}}{{{_latex_num(t, square=True)}}}",
        )
    raise MathServiceError("not enough givens for an acceleration")


_SUVAT_OPS = {
    "suvat_velocity": (_suvat_velocity, "m/s"),
    "suvat_distance": (_suvat_distance, "m"),
    "suvat_time": (_suvat_time, "s"),
    "suvat_acceleration": (_suvat_acceleration, "m/s^2"),
}


def _suvat_graph(op: str, p: dict[str, float], solved: dict[str, float]) -> list[GraphBlockSpec]:
    """A plot of the quantity the question actually asked for.

    Every op used to get the same velocity-against-time line, on the reasoning
    that its slope *is* the acceleration. That is true and it was still wrong:
    "how far does a car go in 5 s" was answered 37.50 m under a chart climbing
    to 15 m/s. The 37.50 is the area under that line — a real relationship, and
    not the one on screen, with nothing saying so. Worse, two different
    questions about the same journey drew byte-identical charts, which reads as
    a duplication bug rather than a wrong axis.

    So a distance question gets distance against time, and the curve bends the
    way s = ut + ½at² bends. Needs u, a and a span; without all three there is
    nothing honest to draw.
    """
    known = {**p, **solved}
    u, a, t_end = known.get("u"), known.get("a"), known.get("t")
    if u is None or a is None or t_end is None or t_end <= 0:
        return []

    # Solving *for* a time plots whichever variable the givens carry to its
    # target: a stated final velocity makes it a velocity question, a stated
    # distance a distance one.
    wants_distance = op == "suvat_distance" or (op == "suvat_time" and "d" in known)

    n_points = 60
    dt = t_end / (n_points - 1)
    if wants_distance:
        points = [
            [round(i * dt, 4), round(u * (i * dt) + 0.5 * a * (i * dt) ** 2, 4)]
            for i in range(n_points)
        ]
        spec = GraphBlockSpec(
            type="trajectory",
            expr=f"s(t) = {u:g}*t + {0.5 * a:g}*t^2",
            variable="t",
            x_min=0.0,
            x_max=t_end,
            points=points,
            title="Distance vs. Time",
            x_label="Time (s)",
            y_label="Distance (m)",
            trajectory_type="position_vs_time",
        )
    else:
        points = [[round(i * dt, 4), round(u + a * (i * dt), 4)] for i in range(n_points)]
        spec = GraphBlockSpec(
            type="trajectory",
            expr=f"v(t) = {u:g} + {a:g}*t",
            variable="t",
            x_min=0.0,
            x_max=t_end,
            points=points,
            title="Velocity vs. Time",
            x_label="Time (s)",
            y_label="Velocity (m/s)",
            trajectory_type="velocity_vs_time",
        )
    return [spec]


def solve_suvat(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "suvat_velocity"
    entry = _SUVAT_OPS.get(op)
    if entry is None:
        raise MathServiceError(f"unsupported suvat op: {op}")
    compute, unit = entry

    value, workings = compute(p)
    if not math.isfinite(value):
        raise MathServiceError("suvat solution is not finite")
    # A negative time or distance means the givens describe no real motion —
    # better refused than reported, since the arithmetic looks fine either way.
    if op in ("suvat_time", "suvat_distance") and value < 0:
        raise MathServiceError(f"negative {op.removeprefix('suvat_')} from these givens")

    solved = {"suvat_velocity": "v", "suvat_distance": "d", "suvat_time": "t"}.get(op)
    graphs = _suvat_graph(op, p, {solved: value} if solved else {})
    return PhysicsResult(
        answer=rf"{workings} \approx {value:.2f} \text{{ {unit} }}",
        answer_value=f"{value:.2f} {unit}",
        graph_specs=graphs,
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
    # No default. The extractor's `range` initializer was one half of the bug
    # this fixes; leaving the other half here would keep an opless intent
    # answering with a distance instead of failing where it can be seen.
    op = intent.physics_op or ""
    h0 = p.get("h0", 0.0)

    if op == "launch_angle":
        # The one op whose unknown is the angle, so it is answered before the
        # angle is read: R = v0² sin(2θ)/g inverted. Two angles give the same
        # range (theta and 90 deg - theta); the low one is what people mean.
        if v0 <= 0:
            raise MathServiceError("launch speed must be positive")
        r_target = p["d"]
        ratio = r_target * g / (v0 * v0)
        if not -1.0 <= ratio <= 1.0:
            raise MathServiceError("that range is out of reach at this speed")
        theta_val = 0.5 * math.asin(ratio)
        deg_val = math.degrees(theta_val)
        return PhysicsResult(
            answer=(
                rf"\theta = \tfrac{{1}}{{2}} \arcsin\!\left(\frac{{Rg}}{{v_0^2}}\right) = "
                rf"\tfrac{{1}}{{2}} \arcsin\!\left(\frac{{{r_target:g} \cdot {g:g}}}"
                rf"{{{_latex_num(v0, square=True)}}}\right) \approx {deg_val:.2f}^\circ"
            ),
            answer_value=f"{deg_val:.2f} deg",
        )

    theta = p["angle"]  # radians (converted by _params_in_si)

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
    elif op == "time_of_flight":
        # t_flight is already in hand — both branches above compute it to build
        # the trajectory, whatever the question asked for.
        answer_latex = (
            rf"t = \frac{{2 v_0 \sin(\theta)}}{{g}} = "
            rf"\frac{{2 \cdot {v0:g} \cdot \sin({math.degrees(theta):.1f}^\circ)}}{{{g:g}}} "
            rf"\approx {t_flight:.2f} \text{{ s}}"
            if h0 <= 0
            else rf"\tfrac{{1}}{{2}} g t^2 - v_0 \sin(\theta) t - h_0 = 0 "
            rf"\Rightarrow t \approx {t_flight:.2f} \text{{ s}}"
        )
        answer_value = f"{t_flight:.2f} s"
    elif op == "impact_speed":
        v_x = v0 * math.cos(theta)
        v_y = v0 * math.sin(theta) - g * t_flight
        speed_val = math.hypot(v_x, v_y)
        answer_latex = (
            rf"v = \sqrt{{v_x^2 + v_y^2}} = "
            rf"\sqrt{{{v_x:.2f}^2 + ({v_y:.2f})^2}} "
            rf"\approx {speed_val:.2f} \text{{ m/s}}"
        )
        answer_value = f"{speed_val:.2f} m/s"
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

    # The same samples, as a scene rather than a plot. The graph answers "what
    # shape is the path"; this answers "what is moving, and what is pulling on
    # it" — and they share one array, so the ball cannot be somewhere the
    # curve is not.
    peak = max(point[1] for point in points)
    span = points[-1][0]
    scene = SimulationBlockSpec(
        type="projectile_motion",
        title="Projectile",
        bodies=[SimulationBody(path=points, radius=max(span, peak) * 0.025 or 0.1)],
        x_min=0.0,
        x_max=span * 1.05,
        y_min=0.0,
        # Headroom so the gravity arrow at the apex is not clipped by the top.
        y_max=max(peak * 1.25, span * 0.25, 1.0),
        arrows=["velocity", "gravity"],
        ground=True,
    )
    return PhysicsResult(
        answer=answer_latex,
        answer_value=answer_value,
        graph_specs=[graph_spec],
        simulation_specs=[scene],
    )


# ---------------------------------------------------------------------------
# Force: F = m a
# ---------------------------------------------------------------------------


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
                SimulationBody(path=heavy, radius=0.3 * (m1 ** (1 / 3)), role="primary"),
                SimulationBody(path=light, radius=0.3 * (m2 ** (1 / 3)), role="secondary"),
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


def solve_force(intent: MathIntent) -> PhysicsResult:
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
            SimulationBody(path=path1, radius=r1, role="primary"),
            SimulationBody(path=path2, radius=r2, role="secondary"),
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


# ---------------------------------------------------------------------------
# Circular motion: a_c = v^2/r, F_c = m v^2/r, T = 2 pi r / v
# ---------------------------------------------------------------------------


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


def solve_circular(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "centripetal_acceleration"
    r = p["r"]
    v = p["v"]
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
        omega_val = abs(v) / r
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
        return PhysicsResult(
            answer=(
                rf"a_c = \frac{{v^2}}{{r}} = \frac{{{_latex_num(v, square=True)}}}{{{r:g}}} "
                rf"\approx {a_c:.2f} \text{{ m/s}}^2"
            ),
            answer_value=f"{a_c:.2f} m/s^2",
            simulation_specs=scene,
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
            simulation_specs=scene,
        )

    raise MathServiceError(f"unsupported circular op: {op}")


# ---------------------------------------------------------------------------
# Springs: F = k x, U = 1/2 k x^2, T = 2 pi sqrt(m/k)
# A pendulum is the same oscillation with T = 2 pi sqrt(L/g), so it lives here
# rather than in a kind of its own.
# ---------------------------------------------------------------------------


def _oscillation_curve(t_period: float, amplitude: float | None) -> GraphBlockSpec:
    """One period-and-a-bit of x(t) = A cos(2πt/T).

    The oscillation is the thing worth seeing, so hand P3's player a curve.
    Amplitude only scales the y-axis — the shape and the period are what the
    question is about — so when none is given the plot is normalised rather
    than invented.
    """
    n_points = 100
    span = 2 * t_period
    dt = span / (n_points - 1)
    a_plot = abs(amplitude) if amplitude else 1.0
    points = [
        [round(i * dt, 4), round(a_plot * math.cos(2 * math.pi * (i * dt) / t_period), 4)]
        for i in range(n_points)
    ]
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


def solve_spring(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "spring_force"

    # A pendulum has a length, not a spring constant, so it is answered before
    # the k lookup below rather than after it.
    if op == "pendulum_period":
        length = p["L"]
        if length <= 0:
            raise MathServiceError("pendulum length must be positive")
        g = p.get("g", 9.81)
        if g <= 0:
            raise MathServiceError("gravity must be positive")
        t_period = 2 * math.pi * math.sqrt(length / g)
        answer = (
            rf"T = 2\pi\sqrt{{\frac{{L}}{{g}}}} = 2\pi\sqrt{{\frac{{{length:g}}}{{{g:g}}}}} "
            rf"\approx {t_period:.2f} \text{{ s}}"
        )
        return PhysicsResult(
            answer=answer,
            answer_value=f"{t_period:.2f} s",
            graph_specs=[_oscillation_curve(t_period, p.get("x"))],
        )

    # Like the pendulum above, these need no spring constant, so they are
    # answered before the k lookup rather than after it.
    if op == "shm_frequency":
        t_period = p["period"]
        if t_period <= 0:
            raise MathServiceError("period must be positive")
        freq = 1 / t_period
        return PhysicsResult(
            answer=(
                rf"f = \frac{{1}}{{T}} = \frac{{1}}{{{t_period:g}}} "
                rf"\approx {freq:.2f} \text{{ Hz}}"
            ),
            answer_value=f"{freq:.2f} Hz",
            graph_specs=[_oscillation_curve(t_period, p.get("x"))],
        )

    if op == "shm_max_speed":
        amplitude = p["x"]
        omega = p["omega"]
        if amplitude <= 0 or omega <= 0:
            raise MathServiceError("amplitude and angular frequency must be positive")
        v_max = amplitude * omega
        return PhysicsResult(
            answer=(
                rf"v_{{max}} = A\omega = {amplitude:g} \cdot {omega:g} "
                rf"\approx {v_max:.2f} \text{{ m/s}}"
            ),
            answer_value=f"{v_max:.2f} m/s",
            graph_specs=[_oscillation_curve(2 * math.pi / omega, amplitude)],
        )

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

        spec = _oscillation_curve(t_period, p.get("x"))
        return PhysicsResult(answer=answer, answer_value=f"{t_period:.2f} s", graph_specs=[spec])

    raise MathServiceError(f"unsupported spring op: {op}")


# ---------------------------------------------------------------------------
# Circuits: V = I R, P = V I, series/parallel resistance
# ---------------------------------------------------------------------------


def solve_circuit(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "current"

    if op in ("series_resistance", "parallel_resistance"):
        # Every R the extractor found, not the first two. Reading three and
        # using two is how "2, 3 and 5 ohms in series" answered 5 ohms.
        resistances = [p[key] for key in sorted(p) if _RESISTOR_KEY_RE.fullmatch(key)]
        if len(resistances) < 2:
            raise MathServiceError("a resistor network needs at least two resistances")
        if any(r <= 0 for r in resistances):
            raise MathServiceError("resistances must be positive")
        terms = " + ".join(f"{r:g}" for r in resistances)
        if op == "series_resistance":
            total = sum(resistances)
            answer = rf"R = \sum R_i = {terms} \approx {total:.2f} \,\Omega"
        else:
            total = 1 / sum(1 / r for r in resistances)
            reciprocals = " + ".join(rf"\frac{{1}}{{{r:g}}}" for r in resistances)
            answer = (
                rf"\frac{{1}}{{R}} = {reciprocals} \Rightarrow R "
                rf"\approx {total:.2f} \,\Omega"
            )
        return PhysicsResult(answer=answer, answer_value=f"{total:.2f} ohm")

    if op == "charge":
        q_val = p["I"] * p["t"]
        return PhysicsResult(
            answer=(rf"Q = I t = {p['I']:g} \cdot {p['t']:g} \approx {q_val:.2f} \text{{ C}}"),
            answer_value=f"{q_val:.2f} C",
        )

    if op == "electrical_energy":
        e_val = p["power"] * p["t"]
        kwh = e_val / 3.6e6
        return PhysicsResult(
            answer=(
                rf"E = P t = {p['power']:g} \cdot {p['t']:g} \approx "
                rf"{e_val:.2f} \text{{ J}} \; ({kwh:.2f} \text{{ kWh}})"
            ),
            answer_value=f"{e_val:.2f} J",
        )

    if op == "capacitance":
        if p["V"] == 0:
            raise MathServiceError("capacitance needs a nonzero voltage")
        c_val = p["Q"] / p["V"]
        return PhysicsResult(
            answer=(
                rf"C = \frac{{Q}}{{V}} = \frac{{{p['Q']:g}}}{{{p['V']:g}}} "
                rf"\approx {c_val:.2f} \text{{ F}}"
            ),
            answer_value=f"{c_val:.2f} F",
        )

    if op == "terminal_voltage":
        v_val = p["E_emf"] - p["I"] * p["r_int"]
        return PhysicsResult(
            answer=(
                rf"V = \varepsilon - I r = {p['E_emf']:g} - {p['I']:g} \cdot "
                rf"{p['r_int']:g} \approx {v_val:.2f} \text{{ V}}"
            ),
            answer_value=f"{v_val:.2f} V",
        )

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
            # The known load on the left, the one whose arm was the question on
            # the right, so the answer is the arm you can see.
            simulation_specs=_lever_scene(
                [
                    (-d1, f1, f"{f1:g} N at {d1:g} m", False),
                    (d2, f2, f"{f2:g} N at {d2:.2f} m", True),
                ]
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
# Dispatch
# ---------------------------------------------------------------------------


def solve_waves(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "wave_frequency_from_period":
        t_period = p["period"]
        if t_period <= 0:
            raise MathServiceError("period must be positive")
        freq = 1 / t_period
        return PhysicsResult(
            answer=(
                rf"f = \frac{{1}}{{T}} = \frac{{1}}{{{t_period:g}}} "
                rf"\approx {freq:.2f} \text{{ Hz}}"
            ),
            answer_value=f"{freq:.2f} Hz",
        )

    if op == "wave_period":
        freq = p["freq"]
        if freq <= 0:
            raise MathServiceError("frequency must be positive")
        t_period = 1 / freq
        return PhysicsResult(
            answer=(
                rf"T = \frac{{1}}{{f}} = \frac{{1}}{{{freq:g}}} "
                rf"\approx {t_period:.4g} \text{{ s}}"
            ),
            answer_value=f"{t_period:.4g} s",
        )

    if op == "doppler_frequency":
        source = p["v_src"]
        sound = p["v_sound"]
        freq = p["freq"]
        if sound - source <= 0:
            raise MathServiceError("a source at or above the speed of sound has no Doppler shift")
        observed = freq * sound / (sound - source)
        motion = "approaching" if source > 0 else "receding"
        return PhysicsResult(
            answer=(
                rf"f' = f\,\frac{{v}}{{v - v_s}} = {freq:g} \cdot "
                rf"\frac{{{sound:g}}}{{{sound:g} - ({source:g})}} "
                rf"\approx {observed:.2f} \text{{ Hz}}"
            ),
            answer_value=f"{observed:.2f} Hz ({motion}, sound at {sound:g} m/s)",
        )

    if op == "wave_speed":
        value = p["freq"] * p["wavelength"]
        return PhysicsResult(
            answer=(
                rf"v = f\lambda = {p['freq']:g} \cdot {p['wavelength']:g} "
                rf"\approx {value:.2f} \text{{ m/s}}"
            ),
            answer_value=f"{value:.2f} m/s",
        )

    if op == "wavelength":
        if p["freq"] <= 0:
            raise MathServiceError("frequency must be positive")
        value = p["v_wave"] / p["freq"]
        return PhysicsResult(
            answer=(
                rf"\lambda = \frac{{v}}{{f}} = \frac{{{p['v_wave']:g}}}{{{p['freq']:g}}} "
                rf"\approx {value:.2f} \text{{ m}}"
            ),
            answer_value=f"{value:.2f} m",
        )

    if op == "wave_frequency":
        if p["wavelength"] <= 0:
            raise MathServiceError("wavelength must be positive")
        value = p["v_wave"] / p["wavelength"]
        return PhysicsResult(
            answer=(
                rf"f = \frac{{v}}{{\lambda}} = "
                rf"\frac{{{p['v_wave']:g}}}{{{p['wavelength']:g}}} "
                rf"\approx {value:.2f} \text{{ Hz}}"
            ),
            answer_value=f"{value:.2f} Hz",
        )

    raise MathServiceError(f"unsupported waves op: {op}")


def solve_optics(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "critical_angle":
        n = p["n1"]
        if n <= 1:
            raise MathServiceError("total internal reflection needs an index above 1")
        theta_c = math.degrees(math.asin(1 / n))
        return PhysicsResult(
            answer=(
                rf"\theta_c = \arcsin\!\left(\frac{{1}}{{n}}\right) = "
                rf"\arcsin\!\left(\frac{{1}}{{{n:g}}}\right) \approx {theta_c:.2f}^\circ"
            ),
            answer_value=f"{theta_c:.2f} deg",
        )

    if op == "refractive_index":
        t1, t2 = p["angle"], p["angle2"]
        if math.sin(t2) == 0:
            raise MathServiceError("the refracted angle cannot be zero")
        n = math.sin(t1) / math.sin(t2)
        return PhysicsResult(
            answer=(
                rf"n = \frac{{\sin\theta_1}}{{\sin\theta_2}} = "
                rf"\frac{{\sin({math.degrees(t1):.1f}^\circ)}}"
                rf"{{\sin({math.degrees(t2):.1f}^\circ)}} \approx {n:.2f}"
            ),
            answer_value=f"{n:.2f}",
        )

    if op == "magnification":
        if p["h_obj"] == 0:
            raise MathServiceError("the object height cannot be zero")
        m_val = p["h_img"] / p["h_obj"]
        return PhysicsResult(
            answer=(
                rf"m = \frac{{h_i}}{{h_o}} = \frac{{{p['h_img']:g}}}{{{p['h_obj']:g}}} "
                rf"\approx {m_val:.2f}"
            ),
            answer_value=f"{m_val:.2f}",
        )

    if op == "image_distance":
        focal, obj = p["focal"], p["d_obj"]
        if focal <= 0 or obj <= 0:
            raise MathServiceError("only a converging lens with a real object is solved here")
        if obj <= focal:
            # Inside the focal length the image is virtual, and the sign that
            # says so is exactly what the conventions disagree about.
            raise MathServiceError("an object inside the focal length forms a virtual image")
        img = 1 / (1 / focal - 1 / obj)
        return PhysicsResult(
            answer=(
                rf"\frac{{1}}{{f}} = \frac{{1}}{{u}} + \frac{{1}}{{v}} \Rightarrow v = "
                rf"\frac{{uf}}{{u - f}} = \frac{{{obj:g} \cdot {focal:g}}}"
                rf"{{{obj:g} - {focal:g}}} \approx {img:.4g} \text{{ m}}"
            ),
            answer_value=f"{img:.4g} m",
        )

    raise MathServiceError(f"unsupported optics op: {op}")


def solve_thermal(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "heat_energy":
        q_val = p["m"] * p["c_heat"] * p["delta_temp"]
        return PhysicsResult(
            answer=(
                rf"Q = mc\Delta T = {p['m']:g} \cdot {p['c_heat']:g} \cdot "
                rf"{p['delta_temp']:g} \approx {q_val:.2f} \text{{ J}}"
            ),
            answer_value=f"{q_val:.2f} J",
        )

    if op == "ideal_gas_pressure":
        volume = p["volume"]
        if volume <= 0:
            raise MathServiceError("volume must be positive")
        if p["temp"] <= 0:
            raise MathServiceError("an absolute temperature must be positive")
        pressure = p["moles"] * _GAS_CONSTANT * p["temp"] / volume
        return PhysicsResult(
            answer=(
                rf"P = \frac{{nRT}}{{V}} = \frac{{{p['moles']:g} \cdot {_GAS_CONSTANT:.4f} "
                rf"\cdot {p['temp']:g}}}{{{volume:g}}} \approx {pressure:.2f} \text{{ Pa}}"
            ),
            answer_value=f"{pressure:.2f} Pa",
        )

    if op == "thermal_efficiency":
        supplied = p["Q_in"]
        if supplied <= 0:
            raise MathServiceError("the energy supplied must be positive")
        eta = p["W_out"] / supplied
        return PhysicsResult(
            answer=(
                rf"\eta = \frac{{W}}{{Q_{{in}}}} = \frac{{{p['W_out']:g}}}{{{supplied:g}}} "
                rf"\approx {eta:.2f} \; ({eta * 100:.1f}\%)"
            ),
            answer_value=f"{eta:.2f} ({eta * 100:.1f}%)",
        )

    raise MathServiceError(f"unsupported thermal op: {op}")


def solve_gravitation(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "gravitational_force":
        r = p["r"]
        if r <= 0:
            raise MathServiceError("separation must be positive")
        f_val = _BIG_G * p["m1"] * p["m2"] / (r * r)
        return PhysicsResult(
            answer=(
                rf"F = \frac{{G m_1 m_2}}{{r^2}} = \frac{{{_BIG_G:.5g} \cdot {p['m1']:g} "
                rf"\cdot {p['m2']:g}}}{{{_latex_num(r, square=True)}}} "
                rf"\approx {f_val:.4g} \text{{ N}}"
            ),
            answer_value=f"{f_val:.4g} N",
        )

    if op == "orbital_velocity":
        r = p["radius_body"] + p.get("altitude", 0.0)
        if r <= 0:
            raise MathServiceError("orbital radius must be positive")
        v_val = math.sqrt(_BIG_G * p["M"] / r)
        return PhysicsResult(
            answer=(
                rf"v = \sqrt{{\frac{{GM}}{{r}}}} = \sqrt{{\frac{{{_BIG_G:.5g} \cdot "
                rf"{p['M']:.4g}}}{{{r:.4g}}}}} \approx {v_val:.2f} \text{{ m/s}}"
            ),
            answer_value=f"{v_val:.2f} m/s",
            simulation_specs=[_orbit_scene(r)],
        )

    if op == "escape_velocity":
        radius = p["radius_body"]
        if radius <= 0:
            raise MathServiceError("radius must be positive")
        v_val = math.sqrt(2 * _BIG_G * p["M"] / radius)
        return PhysicsResult(
            answer=(
                rf"v_e = \sqrt{{\frac{{2GM}}{{R}}}} = \sqrt{{\frac{{2 \cdot {_BIG_G:.5g} "
                rf"\cdot {p['M']:.4g}}}{{{radius:.4g}}}}} \approx {v_val:.2f} \text{{ m/s}}"
            ),
            answer_value=f"{v_val:.2f} m/s",
        )

    if op == "surface_gravity":
        radius = p["radius_body"]
        if radius <= 0:
            raise MathServiceError("radius must be positive")
        g_val = _BIG_G * p["M"] / (radius * radius)
        return PhysicsResult(
            answer=(
                rf"g = \frac{{GM}}{{R^2}} = \frac{{{_BIG_G:.5g} \cdot {p['M']:.4g}}}"
                rf"{{{_latex_num(radius, square=True)}}} \approx {g_val:.2f} "
                rf"\text{{ m/s}}^2"
            ),
            answer_value=f"{g_val:.2f} m/s^2",
        )

    raise MathServiceError(f"unsupported gravitation op: {op}")


def solve_fluids(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "pressure_from_force":
        area = p["area"]
        if area <= 0:
            raise MathServiceError("area must be positive")
        pressure = p["F"] / area
        return PhysicsResult(
            answer=(
                rf"P = \frac{{F}}{{A}} = \frac{{{p['F']:g}}}{{{area:g}}} "
                rf"\approx {pressure:.2f} \text{{ Pa}}"
            ),
            answer_value=f"{pressure:.2f} Pa",
        )

    if op == "pressure_at_depth":
        pressure = p["rho"] * p.get("g", 9.81) * p["depth"]
        return PhysicsResult(
            answer=(
                rf"P = \rho g h = {p['rho']:g} \cdot {p.get('g', 9.81):g} \cdot "
                rf"{p['depth']:g} \approx {pressure:.2f} \text{{ Pa}}"
            ),
            # Gauge, and it says so: the absolute reading is this plus one
            # atmosphere, and which one is meant changes the number by 101 kPa.
            answer_value=f"{pressure:.2f} Pa (gauge)",
        )

    if op == "upthrust":
        force = p["rho"] * p["volume"] * p.get("g", 9.81)
        return PhysicsResult(
            answer=(
                rf"F_b = \rho V g = {p['rho']:g} \cdot {p['volume']:g} \cdot "
                rf"{p.get('g', 9.81):g} \approx {force:.2f} \text{{ N}}"
            ),
            answer_value=f"{force:.2f} N",
            # The one fluids answer a free body actually draws: an upward
            # buoyant force against the weight it opposes.
            simulation_specs=_free_body_scene(
                [
                    SimulationVector(
                        anchor=[0.0, 0.0],
                        dx=0.0,
                        dy=1.0,
                        label=f"upthrust {force:.1f} N",
                        role="force",
                    ),
                    SimulationVector(
                        anchor=[0.0, 0.0], dx=0.0, dy=-1.0, label="weight", role="force"
                    ),
                ],
                label="body",
            ),
        )

    if op == "density":
        volume = p["volume"]
        if volume <= 0:
            raise MathServiceError("volume must be positive")
        rho = p["m"] / volume
        return PhysicsResult(
            answer=(
                rf"\rho = \frac{{m}}{{V}} = \frac{{{p['m']:g}}}{{{volume:g}}} "
                rf"\approx {rho:.2f} \text{{ kg/m}}^3"
            ),
            answer_value=f"{rho:.2f} kg/m^3",
        )

    if op == "continuity_velocity":
        a2 = p["A2"]
        if a2 <= 0:
            raise MathServiceError("the second area must be positive")
        v2 = p["A1"] * p["v"] / a2
        return PhysicsResult(
            answer=(
                rf"A_1 v_1 = A_2 v_2 \Rightarrow v_2 = \frac{{{p['A1']:g} \cdot "
                rf"{p['v']:g}}}{{{a2:g}}} \approx {v2:.2f} \text{{ m/s}}"
            ),
            answer_value=f"{v2:.2f} m/s",
        )

    if op == "flow_rate":
        flow = p["area"] * p["v"]
        return PhysicsResult(
            answer=(
                rf"Q = A v = {p['area']:g} \cdot {p['v']:g} \approx {flow:.4g} "
                rf"\text{{ m}}^3\text{{/s}}"
            ),
            answer_value=f"{flow:.4g} m^3/s",
        )

    raise MathServiceError(f"unsupported fluids op: {op}")


def solve_rotation(intent: MathIntent) -> PhysicsResult:
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


def solve_magnetism(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "magnetic_force_wire":
        value = p["b_field"] * p["I"] * p["wire_L"]
        return PhysicsResult(
            answer=(
                rf"F = BIL = {p['b_field']:g} \cdot {p['I']:g} \cdot {p['wire_L']:g} "
                rf"\approx {value:.2f} \text{{ N}}"
            ),
            answer_value=f"{value:.2f} N",
        )

    if op == "magnetic_force_charge":
        value = p["Q"] * p["v"] * p["b_field"]
        return PhysicsResult(
            answer=(
                rf"F = qvB = {p['Q']:g} \cdot {p['v']:g} \cdot {p['b_field']:g} "
                rf"\approx {value:.2f} \text{{ N}}"
            ),
            # The full form carries sin(theta); this is the perpendicular case,
            # which is the one every school question states.
            answer_value=f"{value:.2f} N (field perpendicular to the motion)",
        )

    if op == "magnetic_flux":
        value = p["b_field"] * p["area"]
        return PhysicsResult(
            answer=(
                rf"\Phi = BA = {p['b_field']:g} \cdot {p['area']:g} "
                rf"\approx {value:.4g} \text{{ Wb}}"
            ),
            answer_value=f"{value:.4g} Wb",
        )

    raise MathServiceError(f"unsupported magnetism op: {op}")


def solve_materials(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "stress":
        area = p["area"]
        if area <= 0:
            raise MathServiceError("area must be positive")
        value = p["F"] / area
        return PhysicsResult(
            answer=(
                rf"\sigma = \frac{{F}}{{A}} = \frac{{{p['F']:g}}}{{{area:g}}} "
                rf"\approx {value:.4g} \text{{ Pa}}"
            ),
            answer_value=f"{value:.4g} Pa",
        )

    if op == "strain":
        original = p["L0"]
        if original <= 0:
            raise MathServiceError("the original length must be positive")
        value = p["dL"] / original
        return PhysicsResult(
            answer=(
                rf"\varepsilon = \frac{{\Delta L}}{{L_0}} = "
                rf"\frac{{{p['dL']:g}}}{{{original:g}}} \approx {value:.4g}"
            ),
            answer_value=f"{value:.4g}",
        )

    if op == "youngs_modulus":
        strain = p["strain"]
        if strain == 0:
            raise MathServiceError("strain cannot be zero")
        value = p["sigma"] / strain
        return PhysicsResult(
            answer=(
                rf"E = \frac{{\sigma}}{{\varepsilon}} = "
                rf"\frac{{{p['sigma']:g}}}{{{strain:g}}} \approx {value:.4g} \text{{ Pa}}"
            ),
            answer_value=f"{value:.4g} Pa",
        )

    raise MathServiceError(f"unsupported materials op: {op}")


def solve_modern(intent: MathIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "photon_energy":
        value = _PLANCK_H * p["freq"]
        ev = value / _ELEMENTARY_CHARGE
        return PhysicsResult(
            answer=(
                rf"E = hf = {_PLANCK_H:.5g} \cdot {p['freq']:.4g} "
                rf"\approx {value:.4g} \text{{ J}}"
            ),
            answer_value=f"{value:.4g} J ({ev:.2f} eV)",
        )

    if op == "de_broglie_wavelength":
        momentum = p["m"] * p["v"]
        if momentum <= 0:
            raise MathServiceError("momentum must be positive")
        value = _PLANCK_H / momentum
        return PhysicsResult(
            answer=(
                rf"\lambda = \frac{{h}}{{mv}} = \frac{{{_PLANCK_H:.5g}}}"
                rf"{{{p['m']:.4g} \cdot {p['v']:.4g}}} \approx {value:.4g} \text{{ m}}"
            ),
            answer_value=f"{value:.4g} m",
        )

    if op == "half_life_remaining":
        halves = p["n_halves"]
        if halves < 0:
            raise MathServiceError("the number of half lives cannot be negative")
        # Answer in the unit the question used. A sample given in grams should
        # not come back in kilograms; the arithmetic is a ratio either way.
        unit = (intent.physics_units or {}).get("m", "kg")
        given = (intent.physics_params or {}).get("m", p["m"])
        value = given / (2**halves)
        return PhysicsResult(
            answer=(
                rf"N = \frac{{N_0}}{{2^n}} = \frac{{{given:g}}}{{2^{{{halves:g}}}}} "
                rf"\approx {value:.4g} \text{{ {unit}}}"
            ),
            answer_value=f"{value:.4g} {unit}",
        )

    if op == "mass_energy":
        value = p["m"] * _SPEED_OF_LIGHT**2
        return PhysicsResult(
            answer=(
                rf"E = mc^2 = {p['m']:g} \cdot ({_SPEED_OF_LIGHT:.0f})^2 "
                rf"\approx {value:.4g} \text{{ J}}"
            ),
            answer_value=f"{value:.4g} J",
        )

    raise MathServiceError(f"unsupported modern op: {op}")


def solve_physics(intent: MathIntent) -> PhysicsResult:
    """Dispatch to the right solver by intent kind."""
    if intent.kind == "kinematics":
        return solve_kinematics(intent)
    if intent.kind == "suvat":
        return solve_suvat(intent)
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
    if intent.kind == "waves":
        return solve_waves(intent)
    if intent.kind == "optics":
        return solve_optics(intent)
    if intent.kind == "thermal":
        return solve_thermal(intent)
    if intent.kind == "gravitation":
        return solve_gravitation(intent)
    if intent.kind == "fluids":
        return solve_fluids(intent)
    if intent.kind == "rotation":
        return solve_rotation(intent)
    if intent.kind == "magnetism":
        return solve_magnetism(intent)
    if intent.kind == "materials":
        return solve_materials(intent)
    if intent.kind == "modern":
        return solve_modern(intent)
    raise MathServiceError(f"not a physics kind: {intent.kind}")
