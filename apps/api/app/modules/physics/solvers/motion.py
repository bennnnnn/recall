"""Kinematics, SUVAT, and projectile-motion solvers."""

from __future__ import annotations

import math

from app.models.schemas.math import GraphBlockSpec
from app.models.schemas.physics import (
    PhysicsIntent,
    SimulationBlockSpec,
    SimulationBody,
)
from app.modules.physics.solvers.common import (
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
    quadratic_roots,
)
from app.services.solving import SolveServiceError

_RATE_OPERATIONS = {"average_speed", "rate_speed", "rate_distance", "rate_time"}


def _same_unit(left: str, right: str) -> bool:
    """One unit however it is spelled: "hours" is the "h" of "km/h"."""
    from app.modules.physics.givens import unit_expression

    return (unit_expression(left) or left) == (unit_expression(right) or right)


def _rate_number(value: float) -> str:
    """Format a checked scalar without inventing presentation precision."""
    if not math.isfinite(value):
        raise SolveServiceError("rate result must be finite")
    return f"{value:.12g}"


def _shown_degrees(radians: float) -> str:
    """Degree label for a launch angle that was supplied in degrees."""
    deg = math.degrees(radians)
    tenths = round(deg, 1)
    if abs(tenths - round(tenths)) < 1e-9:
        return f"{round(tenths):.0f}"
    return f"{tenths:.1f}"


def _projectile_max_height_substitution(intent: PhysicsIntent) -> str:
    """Peak height with the launch angle in degrees, not the SI radian."""
    from app.modules.physics.display import latex_given

    params = intent.physics_params or {}
    h0 = latex_given(params.get("h0", 0.0))
    return (
        rf"H_{{max}} = {h0} + "
        rf"\frac{{{latex_given(params['v0'])}^2 "
        rf"\sin^2({latex_given(params['angle'])}^\circ)}}"
        rf"{{2 \cdot {latex_given(params['g'])}}}"
    )


def _rate_substitution(intent: PhysicsIntent) -> str:
    """Plugged-in rate row, with the units the question used."""
    from app.modules.physics.display import latex_given, latex_unit

    params = intent.physics_params or {}
    units = intent.physics_units or {}
    op = intent.physics_op
    if op in {"average_speed", "rate_speed"}:
        return (
            rf"v = \frac{{{latex_given(params['d'])}{latex_unit(units.get('d', ''))}}}"
            rf"{{{latex_given(params['t'])}{latex_unit(units.get('t', ''))}}}"
        )
    if op == "rate_distance":
        return (
            rf"d = {latex_given(params['v'])}{latex_unit(units.get('v', ''))} \cdot "
            rf"{latex_given(params['t'])}{latex_unit(units.get('t', ''))}"
        )
    return (
        rf"t = \frac{{{latex_given(params['d'])}{latex_unit(units.get('d', ''))}}}"
        rf"{{{latex_given(params['v'])}{latex_unit(units.get('v', ''))}}}"
    )


def _solve_distance_speed_time(intent: PhysicsIntent) -> PhysicsResult:
    """Solve one closed distance-speed-time request in its supplied units."""
    params = intent.physics_params or {}
    units = intent.physics_units or {}
    op = intent.physics_op
    if op in {"average_speed", "rate_speed"}:
        distance, duration = params.get("d"), params.get("t")
        distance_unit, time_unit = units.get("d"), units.get("t")
        if (
            distance is None
            or duration is None
            or distance_unit is None
            or time_unit is None
            or distance < 0
            or duration <= 0
        ):
            raise SolveServiceError("speed requires a non-negative distance and positive time")
        value = distance / duration
        answer_unit = f"{distance_unit}/{time_unit}"
        formula = r"v = \frac{d}{t}"
        working = (
            rf"v = \frac{{d}}{{t}} = "
            rf"\frac{{{_rate_number(distance)}\,\mathrm{{{distance_unit}}}}}"
            rf"{{{_rate_number(duration)}\,\mathrm{{{time_unit}}}}} = "
            rf"{_rate_number(value)}\,\mathrm{{{answer_unit}}}"
        )
    elif op == "rate_distance":
        speed, duration = params.get("v"), params.get("t")
        speed_unit, time_unit = units.get("v"), units.get("t")
        if (
            speed is None
            or duration is None
            or speed_unit is None
            or time_unit is None
            or speed < 0
            or duration < 0
            or "/" not in speed_unit
        ):
            raise SolveServiceError("distance requires a non-negative speed and time")
        distance_unit, speed_time_unit = speed_unit.split("/", 1)
        if not _same_unit(speed_time_unit, time_unit):
            raise SolveServiceError("speed and time units must use the same time scale")
        value = speed * duration
        answer_unit = distance_unit
        formula = r"d = vt"
        working = (
            rf"d = vt = "
            rf"{_rate_number(speed)}\,\mathrm{{{speed_unit}}} \cdot "
            rf"{_rate_number(duration)}\,\mathrm{{{time_unit}}} = "
            rf"{_rate_number(value)}\,\mathrm{{{answer_unit}}}"
        )
    elif op == "rate_time":
        distance, speed = params.get("d"), params.get("v")
        distance_unit, speed_unit = units.get("d"), units.get("v")
        if (
            distance is None
            or speed is None
            or distance_unit is None
            or speed_unit is None
            or distance < 0
            or speed <= 0
            or "/" not in speed_unit
        ):
            raise SolveServiceError("time requires a non-negative distance and positive speed")
        speed_distance_unit, answer_unit = speed_unit.split("/", 1)
        if not _same_unit(speed_distance_unit, distance_unit):
            raise SolveServiceError("distance and speed units must use the same length scale")
        value = distance / speed
        formula = r"t = \frac{d}{v}"
        working = (
            rf"t = \frac{{d}}{{v}} = "
            rf"\frac{{{_rate_number(distance)}\,\mathrm{{{distance_unit}}}}}"
            rf"{{{_rate_number(speed)}\,\mathrm{{{speed_unit}}}}} = "
            rf"{_rate_number(value)}\,\mathrm{{{answer_unit}}}"
        )
    else:  # pragma: no cover - caller checks the closed operation set
        raise SolveServiceError(f"unsupported rate operation: {op}")
    return PhysicsResult(
        answer=working,
        formulas=(formula,),
        quantities=(QuantityResult("", value, answer_unit),),
        substitutions=(_rate_substitution(intent),),
    )


def _solve_stopping_distance(intent: PhysicsIntent) -> PhysicsResult:
    """Reaction distance, braking distance, total, and the braking deceleration.

    The chip is the total distance. The other three results stay on the
    substitution rows the direct reply prints.
    """
    from app.modules.physics.display import latex_given

    params = _params_in_si(intent)
    speed = params.get("v")
    reaction_time = params.get("t_react")
    brake_time = params.get("t_brake")
    if (
        speed is None
        or reaction_time is None
        or brake_time is None
        or not math.isfinite(speed)
        or not math.isfinite(reaction_time)
        or not math.isfinite(brake_time)
        or speed <= 0
        or reaction_time < 0
        or brake_time <= 0
    ):
        raise SolveServiceError("stopping distance needs a positive speed and a braking time")
    reaction = speed * reaction_time
    braking = speed * brake_time / 2.0
    total = reaction + braking
    acceleration = -speed / brake_time
    if not all(math.isfinite(item) for item in (reaction, braking, total, acceleration)):
        raise SolveServiceError("stopping distance is not finite")
    speed_text = latex_given(speed)
    react_text = latex_given(reaction_time)
    brake_text = latex_given(brake_time)
    formulas = (
        r"d_r = v t_r",
        r"d_b = \frac{v t_b}{2}",
        r"d = d_r + d_b",
        r"a = -\frac{v}{t_b}",
    )
    substitutions = (
        rf"d_r = {speed_text} \cdot {react_text} = {latex_given(reaction)}",
        rf"d_b = \frac{{{speed_text} \cdot {brake_text}}}{{2}} = {latex_given(braking)}",
        rf"d = {latex_given(reaction)} + {latex_given(braking)} = {latex_given(total)}",
        rf"a = -\frac{{{speed_text}}}{{{brake_text}}} = {latex_given(acceleration)}",
    )
    return PhysicsResult(
        answer=rf"d = {latex_given(total)}\,\mathrm{{m}}",
        formulas=formulas,
        substitutions=substitutions,
        quantities=(QuantityResult("", total, "m"),),
    )


def solve_kinematics(intent: PhysicsIntent) -> PhysicsResult:
    if intent.physics_op in _RATE_OPERATIONS:
        return _solve_distance_speed_time(intent)
    if intent.physics_op == "stopping_distance":
        return _solve_stopping_distance(intent)
    p = _params_in_si(intent)
    g = p.get("g", 9.81)
    h0 = p.get("h0", 0.0)
    v0 = p.get("v0", 0.0)
    op = intent.physics_op or "time_to_ground"
    if g <= 0:
        raise SolveServiceError("gravity must be positive")

    def _time_to_ground() -> float | None:
        # h0 + v0·t - ½g·t² = 0; the first moment after release it is 0.
        valid = [root for root in quadratic_roots(-0.5 * g, v0, h0) if root > 0]
        return valid[0] if valid else None

    # Past impact, h(t) is negative and v(t) is still "in air" — not a fact.
    if op in ("position", "velocity", "speed"):
        t_asked = p.get("t")
        t_land = _time_to_ground()
        if t_asked is not None and t_land is not None and float(t_asked) > t_land:
            raise SolveServiceError("already on the ground")

    if op == "time_to_ground":
        # Solve h(t) = 0 for t > 0.
        landed = _time_to_ground()
        if landed is None:
            raise SolveServiceError("no positive real time to ground")
        t_val = landed
        v0_sq = _latex_num(v0, square=True)
        formula = r"t = \frac{v_0 + \sqrt{v_0^2 + 2 g h_0}}{g}"
        substitution = (
            rf"t = \frac{{{_latex_num(v0)} + \sqrt{{{v0_sq} + 2 \cdot {g:g} \cdot {h0:g}}}}}"
            rf"{{{g:g}}}"
        )
        answer_latex = (
            r"t = \frac{v_0 + \sqrt{v_0^2 + 2 g h_0}}{g} = "
            rf"\frac{{{_latex_num(v0)} + \sqrt{{{v0_sq} + 2 \cdot {g:g} \cdot {h0:g}}}}}"
            rf"{{{g:g}}} "
            rf"\approx {t_val:.2f} \text{{ s}}"
        )
        quantity = QuantityResult("", t_val, "s")
    elif op in ("velocity", "speed"):
        # Need a time — look for a time param, else use time_to_ground.
        t_param = p.get("t")
        impact_without_time = t_param is None
        if t_param is None:
            landed = _time_to_ground()
            if landed is None:
                raise SolveServiceError("no positive real time to ground")
            t_param = landed
        t_val = float(t_param)
        v_val = float(v0 - g * t_val)
        if impact_without_time:
            impact_magnitude = math.sqrt(v0 * v0 + 2 * g * h0)
            v_val = impact_magnitude if op == "speed" else -impact_magnitude
            symbol = "v" if op == "velocity" else r"v_{impact}"
            sign = "-" if op == "velocity" else ""
            formula = rf"{symbol} = {sign}\sqrt{{v_0^2 + 2gh_0}}"
            substitution = (
                rf"{symbol} = {sign}\sqrt{{{_latex_num(v0, square=True)} + "
                rf"2 \cdot {g:g} \cdot {h0:g}}}"
            )
            answer_latex = (
                rf"{symbol} = {sign}\sqrt{{v_0^2 + 2gh_0}} = "
                rf"{sign}\sqrt{{{_latex_num(v0, square=True)} + 2 \cdot {g:g} \cdot {h0:g}}} "
                rf"\approx {v_val:.2f} \text{{ m/s}}"
            )
        elif op == "speed":
            v_val = abs(v_val)
            formula = r"v = \lvert v_0 - g \cdot t\rvert"
            substitution = rf"v = \lvert {_latex_num(v0)} - {g:g} \cdot {t_val:g}\rvert"
            answer_latex = (
                rf"v = \lvert v_0 - g \cdot t\rvert = "
                rf"\lvert {_latex_num(v0)} - {g:g} \cdot {t_val:g}\rvert "
                rf"\approx {v_val:.2f} \text{{ m/s}}"
            )
        else:
            formula = r"v = v_0 - g t"
            substitution = rf"v = {_latex_num(v0)} - {g:g} \cdot {t_val:g}"
            answer_latex = (
                rf"v = v_0 - g t = {_latex_num(v0)} - {g:g} \cdot {t_val:g} "
                rf"\approx {v_val:.2f} \text{{ m/s}}"
            )
        quantity = QuantityResult("", v_val, "m/s")
    elif op == "position":
        t_param = p.get("t")
        if t_param is None:
            raise SolveServiceError("position requires a time t")
        t_val = float(t_param)
        h_val = float(h0 + v0 * t_val - 0.5 * g * t_val**2)
        formula = r"h = h_0 + v_0 t - \frac{1}{2} g t^2"
        substitution = (
            rf"h = {h0:g} + {_latex_num(v0)} \cdot {t_val:g} - "
            rf"\frac{{1}}{{2}} \cdot {g:g} \cdot {_latex_num(t_val, square=True)}"
        )
        answer_latex = (
            rf"h = h_0 + v_0 t - \frac{{1}}{{2}} g t^2 = "
            rf"{h0:g} + {_latex_num(v0)} \cdot {t_val:g} - "
            rf"\frac{{1}}{{2}} \cdot {g:g} \cdot {_latex_num(t_val, square=True)} "
            rf"\approx {h_val:.2f} \text{{ m}}"
        )
        quantity = QuantityResult("", h_val, "m")
    elif op == "vertical_max_height":
        if v0 <= 0:
            raise SolveServiceError("maximum height for a vertical launch requires v0 > 0")
        h_val = h0 + v0**2 / (2 * g)
        formula = r"h_{\max} = h_0 + \frac{v_0^2}{2g}"
        substitution = (
            rf"h_{{\max}} = {h0:g} + \frac{{{_latex_num(v0, square=True)}}}{{2 \cdot {g:g}}}"
        )
        answer_latex = (
            r"h_{\max} = h_0 + \frac{v_0^2}{2g} = "
            rf"{h0:g} + \frac{{{_latex_num(v0, square=True)}}}{{2 \cdot {g:g}}} "
            rf"\approx {h_val:.2f} \text{{ m}}"
        )
        quantity = QuantityResult("", h_val, "m")
        # The visual shows the complete trip back to the landing plane while
        # the scalar answer remains the requested peak height.
        landed = _time_to_ground()
        if landed is None:
            raise SolveServiceError("no positive real time to ground")
        t_val = landed
    elif op == "acceleration":
        # Constant g for free-fall templates only. The extractor returns
        # None unless a gravity-motion cue is present — do not use this
        # for two-point velocity acceleration.
        answer_latex = rf"a = -g = -{g:g} \text{{ m/s}}^2"
        return PhysicsResult(
            answer=answer_latex,
            formulas=(r"a = -g",),
            substitutions=(rf"a = -{g:g} \text{{ m/s}}^2",),
            quantities=(QuantityResult("", -g, "m/s^2"),),
        )
    else:
        raise SolveServiceError(f"unsupported kinematics op: {op}")

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
            return PhysicsResult(
                answer=answer_latex,
                formulas=(formula,),
                substitutions=(substitution,),
                quantities=(quantity,),
            )
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
            formulas=(formula,),
            substitutions=(substitution,),
            quantities=(quantity,),
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
        return PhysicsResult(
            answer=answer_latex,
            formulas=(formula,),
            substitutions=(substitution,),
            quantities=(quantity,),
        )

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
        formulas=(formula,),
        substitutions=(substitution,),
        quantities=(quantity,),
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


def _suvat_velocity(p: dict[str, float]) -> tuple[float, str, str, str]:
    u, a, t, d = p.get("u"), p.get("a"), p.get("t"), p.get("d")
    if u is not None and a is not None and t is not None:
        plugged = rf"{u:g} + {_latex_num(a)} \cdot {t:g}"
        return u + a * t, rf"v = u + at = {plugged}", r"v = u + at", rf"v = {plugged}"
    if u is not None and a is not None and d is not None:
        square = u * u + 2 * a * d
        if square < 0:
            raise SolveServiceError("no real final velocity: the body stops before that distance")
        plugged = rf"\sqrt{{{_latex_num(u, square=True)} + 2 \cdot {_latex_num(a)} \cdot {d:g}}}"
        return (
            math.sqrt(square),
            rf"v = \sqrt{{u^2 + 2as}} = {plugged}",
            r"v = \sqrt{u^2 + 2as}",
            rf"v = {plugged}",
        )
    if u is not None and d is not None and t is not None:
        if t == 0:
            raise SolveServiceError("time must be non-zero")
        plugged = rf"\frac{{2 \cdot {d:g}}}{{{t:g}}} - {u:g}"
        return (
            2 * d / t - u,
            rf"s = \tfrac{{1}}{{2}}(u + v)t \Rightarrow v = \frac{{2s}}{{t}} - u = {plugged}",
            r"v = \frac{2s}{t} - u",
            rf"v = {plugged}",
        )
    raise SolveServiceError("not enough givens for a final velocity")


def _suvat_distance(p: dict[str, float]) -> tuple[float, str, str, str]:
    u, v, a, t = p.get("u"), p.get("v"), p.get("a"), p.get("t")
    if u is not None and a is not None and t is not None:
        plugged = (
            rf"{u:g} \cdot {t:g} + 0.5 \cdot {_latex_num(a)} \cdot {_latex_num(t, square=True)}"
        )
        return (
            u * t + 0.5 * a * t * t,
            rf"s = ut + \tfrac{{1}}{{2}}at^2 = {plugged}",
            r"s = ut + \tfrac{1}{2}at^2",
            rf"s = {plugged}",
        )
    if u is not None and v is not None and a is not None:
        if a == 0:
            raise SolveServiceError("acceleration must be non-zero to find a distance this way")
        plugged = (
            rf"\frac{{{_latex_num(v, square=True)} - {_latex_num(u, square=True)}}}"
            rf"{{2 \cdot {_latex_num(a)}}}"
        )
        return (
            (v * v - u * u) / (2 * a),
            rf"v^2 = u^2 + 2as \Rightarrow s = \frac{{v^2 - u^2}}{{2a}} = {plugged}",
            r"s = \frac{v^2 - u^2}{2a}",
            rf"s = {plugged}",
        )
    if u is not None and v is not None and t is not None:
        plugged = rf"0.5 \cdot ({u:g} + {v:g}) \cdot {t:g}"
        return (
            0.5 * (u + v) * t,
            rf"s = \tfrac{{1}}{{2}}(u + v)t = {plugged}",
            r"s = \tfrac{1}{2}(u + v)t",
            rf"s = {plugged}",
        )
    raise SolveServiceError("not enough givens for a distance")


def _suvat_time(p: dict[str, float]) -> tuple[float, str, str, str]:
    u, v, a, d = p.get("u"), p.get("v"), p.get("a"), p.get("d")
    if u is not None and v is not None and a is not None:
        if a == 0:
            raise SolveServiceError("acceleration must be non-zero to find a time this way")
        plugged = rf"\frac{{{v:g} - {u:g}}}{{{_latex_num(a)}}}"
        return (
            (v - u) / a,
            rf"v = u + at \Rightarrow t = \frac{{v - u}}{{a}} = {plugged}",
            r"t = \frac{v - u}{a}",
            rf"t = {plugged}",
        )
    if u is not None and a is not None and d is not None:
        # ½at² + ut - s = 0; the earliest non-negative root is the physical one.
        candidates = [root for root in quadratic_roots(0.5 * a, u, -d) if root >= 0]
        if not candidates:
            raise SolveServiceError("the body never reaches that distance")
        return (
            candidates[0],
            rf"s = ut + \tfrac{{1}}{{2}}at^2 \Rightarrow 0.5 \cdot {_latex_num(a)} t^2 + "
            rf"{u:g}t = {d:g}",
            r"\tfrac{1}{2}at^2 + ut - s = 0",
            rf"\tfrac{{1}}{{2}} \cdot {_latex_num(a)} t^2 + {_latex_num(u)} t - {d:g} = 0",
        )
    if u is not None and v is not None and d is not None:
        if u + v == 0:
            raise SolveServiceError("average velocity is zero, so no time follows")
        plugged = rf"\frac{{2 \cdot {d:g}}}{{{u:g} + {v:g}}}"
        return (
            2 * d / (u + v),
            rf"s = \tfrac{{1}}{{2}}(u + v)t \Rightarrow t = \frac{{2s}}{{u + v}} = {plugged}",
            r"t = \frac{2s}{u + v}",
            rf"t = {plugged}",
        )
    raise SolveServiceError("not enough givens for a time")


def _suvat_acceleration(p: dict[str, float]) -> tuple[float, str, str, str]:
    u, v, t, d = p.get("u"), p.get("v"), p.get("t"), p.get("d")
    if u is not None and v is not None and t is not None:
        if t == 0:
            raise SolveServiceError("time must be non-zero")
        plugged = rf"\frac{{{v:g} - {u:g}}}{{{t:g}}}"
        return (
            (v - u) / t,
            rf"v = u + at \Rightarrow a = \frac{{v - u}}{{t}} = {plugged}",
            r"a = \frac{v - u}{t}",
            rf"a = {plugged}",
        )
    if u is not None and v is not None and d is not None:
        if d == 0:
            raise SolveServiceError("distance must be non-zero")
        plugged = (
            rf"\frac{{{_latex_num(v, square=True)} - {_latex_num(u, square=True)}}}"
            rf"{{2 \cdot {d:g}}}"
        )
        return (
            (v * v - u * u) / (2 * d),
            rf"v^2 = u^2 + 2as \Rightarrow a = \frac{{v^2 - u^2}}{{2s}} = {plugged}",
            r"a = \frac{v^2 - u^2}{2s}",
            rf"a = {plugged}",
        )
    if u is not None and t is not None and d is not None:
        if t == 0:
            raise SolveServiceError("time must be non-zero")
        plugged = rf"\frac{{2({d:g} - {u:g} \cdot {t:g})}}{{{_latex_num(t, square=True)}}}"
        return (
            2 * (d - u * t) / (t * t),
            rf"s = ut + \tfrac{{1}}{{2}}at^2 \Rightarrow a = \frac{{2(s - ut)}}{{t^2}} = {plugged}",
            r"a = \frac{2(s - ut)}{t^2}",
            rf"a = {plugged}",
        )
    raise SolveServiceError("not enough givens for an acceleration")


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


def solve_suvat(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "suvat_velocity"
    entry = _SUVAT_OPS.get(op)
    if entry is None:
        raise SolveServiceError(f"unsupported suvat op: {op}")
    compute, unit = entry

    value, workings, formula, substitution = compute(p)
    if not math.isfinite(value):
        raise SolveServiceError("suvat solution is not finite")
    # A negative time or distance means the givens describe no real motion —
    # better refused than reported, since the arithmetic looks fine either way.
    if op in ("suvat_time", "suvat_distance") and value < 0:
        raise SolveServiceError(f"negative {op.removeprefix('suvat_')} from these givens")

    solved = {"suvat_velocity": "v", "suvat_distance": "d", "suvat_time": "t"}.get(op)
    graphs = _suvat_graph(op, p, {solved: value} if solved else {})
    return PhysicsResult(
        answer=rf"{workings} \approx {value:.2f} \text{{ {unit} }}",
        formulas=(formula,),
        substitutions=(substitution,),
        quantities=(QuantityResult("", value, unit),),
        graph_specs=graphs,
    )


# ---------------------------------------------------------------------------
# Projectile: 2D motion at an angle
#   x(t) = v0*cos(θ)*t
#   y(t) = v0*sin(θ)*t - 0.5*g*t^2
#   Range R = v0^2*sin(2θ)/g
#   Max height H = v0^2*sin^2(θ)/(2g)
# ---------------------------------------------------------------------------


def solve_projectile(intent: PhysicsIntent) -> PhysicsResult:
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
        # range, θ and 90° - θ, and both are answers; at the maximum range
        # they coincide at 45°.
        if v0 <= 0:
            raise SolveServiceError("launch speed must be positive")
        r_target = p["d"]
        ratio = r_target * g / (v0 * v0)
        if not -1.0 <= ratio <= 1.0:
            raise SolveServiceError("that range is out of reach at this speed")
        deg_val = math.degrees(0.5 * math.asin(ratio))
        steep = 90.0 - deg_val
        angles = (deg_val,) if math.isclose(deg_val, steep) else (deg_val, steep)
        shown = r" \text{ or } ".join(rf"{angle:.2f}^\circ" for angle in angles)
        return PhysicsResult(
            answer=(
                rf"\theta = \tfrac{{1}}{{2}} \arcsin\!\left(\frac{{Rg}}{{v_0^2}}\right) = "
                rf"\tfrac{{1}}{{2}} \arcsin\!\left(\frac{{{r_target:g} \cdot {g:g}}}"
                rf"{{{_latex_num(v0, square=True)}}}\right) \approx {shown}"
            ),
            formulas=(
                r"\theta = \tfrac{1}{2} \arcsin\!\left(\frac{Rg}{v_0^2}\right)",
                r"\theta' = 90^\circ - \theta",
            ),
            substitutions=(
                rf"\theta = \tfrac{{1}}{{2}} \arcsin\!\left(\frac{{{r_target:g} \cdot {g:g}}}"
                rf"{{{_latex_num(v0, square=True)}}}\right)",
            ),
            quantities=tuple(QuantityResult("", angle, "deg") for angle in angles),
            joiner=" or ",
        )

    theta = p["angle"]  # radians (converted by _params_in_si)

    if h0 > 0:
        # y = h0 + v0 sinθ t - ½ g t² = 0 → ½ g t² - v0 sinθ t - h0 = 0
        a = 0.5 * g
        b = -v0 * math.sin(theta)
        c = -h0
        disc = b * b - 4 * a * c
        if disc < 0:
            raise SolveServiceError("projectile has no positive flight time")
        t_flight = (-b + math.sqrt(disc)) / (2 * a)
    else:
        t_flight = 2 * v0 * math.sin(theta) / g
    if t_flight <= 0:
        raise SolveServiceError("projectile has no positive flight time")

    if op == "range":
        if h0 > 0:
            r_val = v0 * math.cos(theta) * t_flight
        else:
            r_val = v0**2 * math.sin(2 * theta) / g
        deg = math.degrees(theta)
        v0_sq = _latex_num(v0, square=True)
        if h0 <= 0:
            answer_latex = (
                rf"R = \frac{{v_0^2 \sin(2\theta)}}{{g}} = "
                rf"\frac{{{v0_sq} \cdot \sin({deg:.1f}^\circ \cdot 2)}}{{{g:g}}} "
                rf"\approx {r_val:.2f} \text{{ m}}"
            )
            formulas = (r"R = \frac{v_0^2 \sin(2\theta)}{g}",)
            substitutions = (rf"R = \frac{{{v0_sq} \cdot \sin({deg:.1f}^\circ \cdot 2)}}{{{g:g}}}",)
        else:
            answer_latex = rf"R = v_0 \cos(\theta)\, t \approx {r_val:.2f} \text{{ m}}"
            formulas = (r"R = v_0 \cos(\theta)\, t",)
            substitutions = (rf"R = {v0:g}\cos({_shown_degrees(theta)}^\circ)\cdot {t_flight:.2f}",)
        quantity = QuantityResult("", r_val, "m")
    elif op == "max_height":
        h_val = h0 + v0**2 * math.sin(theta) ** 2 / (2 * g)
        answer_latex = (
            rf"H = h_0 + \frac{{v_0^2 \sin^2(\theta)}}{{2g}} = "
            rf"{h_val:.2f} \text{{ m}}"
        )
        quantity = QuantityResult("", h_val, "m")
        formulas = (r"H = h_0 + \frac{v_0^2 \sin^2(\theta)}{2g}",)
        substitutions = (_projectile_max_height_substitution(intent),)
    elif op == "time_of_flight":
        # t_flight is already in hand — both branches above compute it to build
        # the trajectory, whatever the question asked for.
        if h0 <= 0:
            answer_latex = (
                rf"t = \frac{{2 v_0 \sin(\theta)}}{{g}} = "
                rf"\frac{{2 \cdot {v0:g} \cdot \sin({math.degrees(theta):.1f}^\circ)}}{{{g:g}}} "
                rf"\approx {t_flight:.2f} \text{{ s}}"
            )
            formulas = (r"t = \frac{2 v_0 \sin(\theta)}{g}",)
            substitutions = (
                rf"t_{{flight}} = \frac{{2 \cdot {v0:g} \cdot "
                rf"\sin({math.degrees(theta):.1f}^\circ)}}{{{g:g}}}",
            )
        else:
            answer_latex = (
                rf"\tfrac{{1}}{{2}} g t^2 - v_0 \sin(\theta) t - h_0 = 0 "
                rf"\Rightarrow t \approx {t_flight:.2f} \text{{ s}}"
            )
            formulas = (r"\tfrac{1}{2} g t^2 - v_0 \sin(\theta) t - h_0 = 0 \Rightarrow t",)
            substitutions = (
                rf"\tfrac{{1}}{{2}} \cdot {g:g} t^2 - {v0:g}\sin({_shown_degrees(theta)}^\circ)"
                rf" t - {h0:g} = 0",
            )
        quantity = QuantityResult("", t_flight, "s")
    elif op == "impact_speed":
        v_x = v0 * math.cos(theta)
        v_y = v0 * math.sin(theta) - g * t_flight
        speed_val = math.hypot(v_x, v_y)
        answer_latex = (
            rf"v = \sqrt{{v_x^2 + v_y^2}} = "
            rf"\sqrt{{{v_x:.2f}^2 + ({v_y:.2f})^2}} "
            rf"\approx {speed_val:.2f} \text{{ m/s}}"
        )
        quantity = QuantityResult("", speed_val, "m/s")
        formulas = (r"v = \sqrt{v_x^2 + v_y^2}",)
        substitutions = (rf"v_{{impact}} = \sqrt{{{v_x:.2f}^2 + ({v_y:.2f})^2}}",)
    else:
        raise SolveServiceError(f"unsupported projectile op: {op}")

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

    flat = f"x*tan({math.degrees(theta):.1f} deg) - g*x^2/(2*v0^2*cos^2(theta))"
    expr = f"y(x) = {h0:g} + {flat}" if h0 > 0 else f"y(x) = {flat}"
    graph_spec = GraphBlockSpec(
        type="trajectory",
        expr=expr,
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
        quantities=(quantity,),
        formulas=formulas,
        substitutions=substitutions,
        graph_specs=[graph_spec],
        simulation_specs=[scene],
    )
