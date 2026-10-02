"""Vertical kinematics under gravity: time to the ground, velocity, position, peak height
and acceleration. Rate and stopping-distance questions go to their own solvers.
"""

from __future__ import annotations

import math

from app.models.schemas.math import GraphBlockSpec
from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solvers.common import (
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
    quadratic_roots,
)
from app.modules.physics.solvers.rates import _RATE_OPERATIONS, _solve_distance_speed_time
from app.modules.physics.solvers.stopping import _solve_stopping_distance
from app.services.solving import SolveServiceError


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
