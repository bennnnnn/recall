"""Distance, speed and time: d = vt and average speed, shown in the question's units."""

from __future__ import annotations

import math

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solvers.common import PhysicsResult, QuantityResult
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
