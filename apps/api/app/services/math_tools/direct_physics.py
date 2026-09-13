"""Complete literal physics requests may display their existing verified result.

This grammar validates quantities and their roles; it does not solve equations
or discard extra clauses. The block carries the exact intent that was solved.
"""

from __future__ import annotations

import math
import re
from typing import Any

from app.models.schemas.math import MathIntent
from app.services.math_tools.block.common import VerifiedMathBlock
from app.services.math_tools.physics import _LENGTH_UNIT_PATTERN, _VELOCITY_UNIT_PATTERN

_NUMBER = r"-?(?:[0-9]{1,12}(?:\.[0-9]{1,12})?|\.[0-9]{1,12})"
_TIME = r"seconds?|s|minutes?|min|milliseconds?|ms|hours?|hr|h"
_MASS = r"kg|mg|g|lbs|lb|oz"
_ACCELERATION = r"m/s\^?2"
_ASK = r"(?:find|calculate|compute|determine|what is) (?:the|its) "
_GRAVITY = re.compile(rf"g\s*=\s*(?P<g>{_NUMBER})(?:\s+m/s\^?2)?", re.IGNORECASE)


def _quantity(name: str, unit: str) -> str:
    return rf"(?P<{name}>{_NUMBER})\s*(?P<{name}_unit>{unit})"


_DROP = re.compile(
    r"(?:a|an) (?:ball|object|stone) is "
    r"(?:dropped from(?: a height of)?|in free fall from) "
    + _quantity("h0", _LENGTH_UNIT_PATTERN)
    + r"\. "
    + _ASK
    + r"(?P<quantity>time to (?:the )?ground|velocity|speed|height|acceleration)"
    + rf"(?: after {_quantity('t', _TIME)})?",
    re.IGNORECASE,
)
_PROJECTILE = re.compile(
    r"a projectile is launched at "
    + _quantity("v0", _VELOCITY_UNIT_PATTERN)
    + r" at "
    + _quantity("angle", r"degrees?|deg|°")
    + r"\. "
    + _ASK
    + r"(?P<quantity>range|maximum height)",
    re.IGNORECASE,
)
_FORCE = (
    (
        "force",
        re.compile(
            _ASK
            + r"force on a "
            + _quantity("m", _MASS)
            + r" object with acceleration "
            + _quantity("a", _ACCELERATION),
            re.IGNORECASE,
        ),
    ),
    (
        "acceleration",
        re.compile(
            _ASK
            + r"acceleration of a "
            + _quantity("m", _MASS)
            + r" object under a force of "
            + _quantity("F", "N"),
            re.IGNORECASE,
        ),
    ),
    (
        "mass",
        re.compile(
            _ASK
            + r"mass of an object with force "
            + _quantity("F", "N")
            + r" and acceleration "
            + _quantity("a", _ACCELERATION),
            re.IGNORECASE,
        ),
    ),
)
_ENERGY = (
    (
        "kinetic_energy",
        re.compile(
            _ASK
            + r"kinetic energy of a "
            + _quantity("m", _MASS)
            + r" object moving at "
            + _quantity("v", _VELOCITY_UNIT_PATTERN),
            re.IGNORECASE,
        ),
    ),
    (
        "potential_energy",
        re.compile(
            _ASK
            + r"potential energy of a "
            + _quantity("m", _MASS)
            + r" object at (?:a )?height (?:of )?"
            + _quantity("h", _LENGTH_UNIT_PATTERN),
            re.IGNORECASE,
        ),
    ),
    (
        "work",
        re.compile(
            _ASK
            + r"work done by a force of "
            + _quantity("F", "N")
            + r" over a distance of "
            + _quantity("d", _LENGTH_UNIT_PATTERN),
            re.IGNORECASE,
        ),
    ),
    (
        "power",
        re.compile(
            _ASK
            + r"power of a force of "
            + _quantity("F", "N")
            + r" moving at "
            + _quantity("v", _VELOCITY_UNIT_PATTERN),
            re.IGNORECASE,
        ),
    ),
)
_AVERAGE_SPEED = re.compile(
    _ASK
    + r"average speed for "
    + _quantity("d", _LENGTH_UNIT_PATTERN)
    + r" in "
    + _quantity("t", _TIME),
    re.IGNORECASE,
)


def _request(text: str) -> tuple[str, float, bool] | None:
    if len(text) > 1000:
        return None
    request = " ".join(text.split()).replace("\u2212", "-").rstrip(".?")
    if request.lower().startswith("please "):
        request = request[7:]
    body, separator, gravity = request.lower().rpartition(". use ")
    if not separator:
        return request, 9.81, False
    match = _GRAVITY.fullmatch(gravity)
    if match is None:
        return None
    g = float(match["g"])
    if not 0 < g <= 1e6:
        return None
    # Slice the original string so SI unit case is never discarded.
    return request[: len(body)], g, True


def _measures(match: re.Match[str]) -> tuple[dict[str, float], dict[str, str]]:
    groups = match.groupdict()
    params = {
        key[:-5]: float(groups[key[:-5]])
        for key, value in groups.items()
        if key.endswith("_unit") and value is not None
    }
    units = {
        key[:-5]: value
        for key, value in groups.items()
        if key.endswith("_unit") and value is not None
    }
    return params, units


def _expected_intent(text: str) -> MathIntent | None:
    parsed = _request(text)
    if parsed is None:
        return None
    body, g, explicit_g = parsed
    match = _DROP.fullmatch(body)
    if match:
        params, units = _measures(match)
        quantity = match["quantity"].lower()
        op = {
            "height": "position",
            "time to ground": "time_to_ground",
            "time to the ground": "time_to_ground",
        }.get(quantity, quantity)
        if params["h0"] <= 0 or ("t" in params) != (op in {"position", "velocity", "speed"}):
            return None
        if "t" in params and params["t"] <= 0:
            return None
        params.update(g=g, v0=0.0)
        units.update(g="m/s^2", v0="m/s")
        return _intent("kinematics", op, params, units)
    match = _PROJECTILE.fullmatch(body)
    if match:
        params, units = _measures(match)
        if params["v0"] <= 0 or not 0 < params["angle"] < 90:
            return None
        params["g"] = g
        units.update(g="m/s^2", angle="deg")
        op = "range" if match["quantity"].lower() == "range" else "max_height"
        return _intent("projectile", op, params, units)
    for quantity, pattern in _FORCE:
        match = pattern.fullmatch(body)
        if match is None or explicit_g:
            continue
        params, units = _measures(match)
        if "m" in params and params["m"] <= 0:
            return None
        if quantity == "mass" and (params["a"] == 0 or params["F"] / params["a"] <= 0):
            return None
        return _intent("force", "net_force", params, units)
    for op, pattern in _ENERGY:
        match = pattern.fullmatch(body)
        if match is None or (explicit_g and op != "potential_energy"):
            continue
        params, units = _measures(match)
        if ("m" in params and params["m"] <= 0) or ("d" in params and params["d"] < 0):
            return None
        if op == "potential_energy":
            params["g"] = g
            units["g"] = "m/s^2"
        return _intent("energy", op, params, units)
    match = _AVERAGE_SPEED.fullmatch(body)
    if match is not None and not explicit_g:
        params, _units = _measures(match)
        if not 0 <= params["d"] <= 1e6 or not 0 < params["t"] <= 1e6:
            return None
        from app.services.math_tools.school import _extract_average_speed_intent

        intent = _extract_average_speed_intent(body)
        if intent is not None and intent.expr == f"{params['d']}/{params['t']}":
            return intent
    return None


def _intent(
    kind: str, op: str, params: dict[str, float], units: dict[str, str]
) -> MathIntent | None:
    if any(not math.isfinite(value) or abs(value) > 1e6 for value in params.values()):
        return None
    return MathIntent.model_validate(
        {
            "kind": kind,
            "physics_op": op,
            "physics_params": params,
            "physics_units": units,
            "operation": "solve",
        }
    )


def can_direct_physics(
    verified: VerifiedMathBlock, text: str, fences: list[dict[str, Any]]
) -> bool:
    expected = _expected_intent(text)
    if expected is None or expected != verified.physics_intent:
        return False
    answer = verified.canonical_answer
    if not answer or len(answer) > 400 or len(fences) != 1:
        return False
    fence = fences[0]
    if expected.kind in {"force", "energy", "arithmetic"} or expected.physics_op == "acceleration":
        return fence.get("type") == "answer" and fence.get("content") == answer
    if fence.get("type") != "trajectory" or fence.get("expr2") or fence.get("points2"):
        return False
    points = fence.get("points")
    return bool(
        isinstance(points, list)
        and len(points) >= 2
        and all(
            isinstance(point, list)
            and len(point) == 2
            and all(type(value) in {int, float} and math.isfinite(value) for value in point)
            for point in points
        )
        and all(
            type(fence.get(key)) in {int, float} and math.isfinite(fence[key])
            for key in ("x_min", "x_max")
        )
        and fence["x_min"] < fence["x_max"]
        and fence.get("trajectory_type")
        == ("parametric" if expected.kind == "projectile" else "position_vs_time")
    )
