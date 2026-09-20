"""Complete literal physics requests may display their existing verified result.

This grammar validates quantities and their roles; it does not solve equations
or discard extra clauses. The block carries the exact intent that was solved.
"""

from __future__ import annotations

import math
import re
from typing import Any

from app.models.schemas.math import MathIntent
from app.models.schemas.physics import PhysicsIntent
from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES
from app.services.physics.extract import _LENGTH_UNIT_PATTERN, _VELOCITY_UNIT_PATTERN
from app.services.solving import VerifiedMathBlock

_NUMBER = r"-?(?:[0-9]{1,12}(?:\.[0-9]{1,12})?|\.[0-9]{1,12})"
_TIME = r"seconds?|s|minutes?|min|milliseconds?|ms|hours?|hr|h"
_MASS = r"kg|mg|g|lbs|lb|oz"
_ACCELERATION = r"m/s\^?2"
_ASK = r"(?:find|calculate|compute|determine|what is) (?:the|its) "
_GRAVITY = re.compile(rf"g\s*=\s*(?P<g>{_NUMBER})(?:\s+m/s\^?2)?", re.IGNORECASE)
_EXTRA_REQUEST = re.compile(
    r"\b(?:hint|air resistance|drag|wind|convert the answer|convert (?:it|this|that))\b"
    r"|\b(?:and|also|then)\s+(?:solve|calculate|compute|find|convert|explain|show|tell)\b",
    re.IGNORECASE,
)


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


def _expected_intent(text: str) -> MathIntent | PhysicsIntent | None:
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
        from app.services.math.tools.school import extract_average_speed_intent

        intent = extract_average_speed_intent(body)
        if intent is not None and intent.expr == f"{params['d']}/{params['t']}":
            return intent
    return None


def _intent(
    kind: str, op: str, params: dict[str, float], units: dict[str, str]
) -> PhysicsIntent | None:
    if any(not math.isfinite(value) or abs(value) > 1e6 for value in params.values()):
        return None
    return PhysicsIntent.model_validate(
        {
            "kind": kind,
            "physics_op": op,
            "physics_params": params,
            "physics_units": units,
            "operation": "solve",
        }
    )


def _expected_trajectory_type(intent: PhysicsIntent) -> str:
    """The one ``trajectory_type`` ``solve_physics`` emits for this intent.

    Must stay in lockstep with ``solve_kinematics`` / ``solve_projectile``. This
    guard exists to prove the fence came from that solve rather than from the
    model, so an extra value here would be a hole — and a missing one silently
    drops the whole direct reply, which is the harder failure to notice.
    """
    if intent.kind == "projectile":
        return "parametric"
    if intent.physics_op in ("velocity", "speed"):
        return "velocity_vs_time"
    return "position_vs_time"


def can_direct_physics(
    verified: VerifiedMathBlock, text: str, fences: list[dict[str, Any]]
) -> bool:
    expected = _expected_intent(text)
    intent = verified.physics_intent
    if intent is None:
        return False
    answer = verified.canonical_answer
    # P14 attaches a scene alongside the trajectory graph, so a projectile
    # carries two fences where the rule below expects one. A scene is not a
    # second answer — it is an illustration of the same one, server-owned and
    # never model-written — so it is set aside before the count rather than
    # counted. Without this, adding the scene silently switched every
    # projectile back to the provider path: this returned False, the
    # pre-computed reply was dropped, and nothing anywhere reported it.
    answering = [f for f in fences if f.get("type") not in SIMULATION_SPEC_TYPES]
    if not answer or len(answer) > 800 or len(answering) != 1:
        return False
    if isinstance(intent, PhysicsIntent) and not verified.physics_working:
        return False
    fence = answering[0]
    # The legacy exact grammars remain a useful second check for their closed
    # subset. Every other physics kind is already guarded by deterministic
    # extraction plus a solver-owned canonical fence, so it can return without
    # waiting for a language model as well.
    if expected is None:
        if not isinstance(intent, PhysicsIntent):
            return False
        if _EXTRA_REQUEST.search(text):
            return False
        if fence.get("type") == "answer":
            return fence.get("content") == answer
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
        )
    if expected != intent:
        return False
    if not isinstance(expected, PhysicsIntent):
        # Only the average-speed cross-check (a MathIntent, kind="arithmetic")
        # reaches here — it has no trajectory, just a scalar answer.
        return fence.get("type") == "answer" and fence.get("content") == answer
    if expected.kind in {"force", "energy"} or expected.physics_op == "acceleration":
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
        and fence.get("trajectory_type") == _expected_trajectory_type(expected)
    )


_SYMBOLS = {
    "angle": r"\theta",
    "h0": r"h_0",
    "v0": r"v_0",
    "d_obj": "u",
    "focal": "f",
    "delta_temp": r"\Delta T",
    "c_heat": "c",
    "b_field": "B",
    "wire_L": "L",
    "radius_body": "R",
    "inertia": "I",
    "wavelength": r"\lambda",
    "freq": "f",
}

_RESULT_SYMBOLS = {
    "position": "h",
    "velocity": "v",
    "time_to_ground": "t",
    "speed": "v",
    "acceleration": "a",
    "range": "R",
    "max_height": "H_{max}",
    "time_of_flight": "t_{flight}",
    "impact_speed": "v_{impact}",
    "launch_angle": r"\theta",
    "net_force": "F",
    "tension": "T",
    "atwood": r"a,\ T",
    "resultant_force": "R",
    "resolve_force": r"F_x,\ F_y",
    "kinetic_energy": "KE",
    "potential_energy": "PE",
    "work": "W",
    "power": "P",
    "momentum": "p",
    "impulse": "J",
    "final_velocity": "v_f",
    "friction_force": "f",
    "normal_force": "N",
    "incline_acceleration": "a",
    "friction_coefficient": r"\mu",
    "minimum_force": "F_{min}",
    "centripetal_force": "F_c",
    "centripetal_acceleration": "a_c",
    "orbital_period": "T",
    "angular_velocity": r"\omega",
    "spring_force": "F",
    "spring_energy": "E_s",
    "shm_period": "T",
    "pendulum_period": "T",
    "shm_frequency": "f",
    "shm_max_speed": "v_{max}",
    "voltage": "V",
    "current": "I",
    "resistance": "R",
    "electrical_power": "P",
    "series_resistance": "R_s",
    "parallel_resistance": "R_p",
    "charge": "Q",
    "electrical_energy": "E",
    "capacitance": "C",
    "terminal_voltage": "V_{terminal}",
    "torque": r"\tau",
    "moment_balance": "d_2",
    "suvat_velocity": "v",
    "suvat_distance": "s",
    "suvat_time": "t",
    "suvat_acceleration": "a",
    "wave_speed": "v",
    "wavelength": r"\lambda",
    "wave_frequency": "f",
    "wave_frequency_from_period": "f",
    "wave_period": "T",
    "doppler_frequency": "f'",
    "image_distance": "v",
    "magnification": "m",
    "refractive_index": "n",
    "critical_angle": r"\theta_c",
    "heat_energy": "Q",
    "ideal_gas_pressure": "P",
    "thermal_efficiency": r"\eta",
    "gravitational_force": "F",
    "orbital_velocity": "v",
    "escape_velocity": "v_e",
    "surface_gravity": "g",
    "pressure_from_force": "P",
    "pressure_at_depth": "P",
    "upthrust": "F_b",
    "density": r"\rho",
    "continuity_velocity": "v_2",
    "flow_rate": "Q",
    "moment_of_inertia": "I",
    "angular_momentum": "L",
    "rotational_kinetic_energy": "E_k",
    "magnetic_force_wire": "F",
    "magnetic_force_charge": "F",
    "magnetic_flux": r"\Phi",
    "stress": r"\sigma",
    "strain": r"\varepsilon",
    "youngs_modulus": "E",
    "half_life_remaining": "N",
    "mass_energy": "E",
    "photon_energy": "E",
    "de_broglie_wavelength": r"\lambda",
    "lever_arm": "d",
    "net_torque": r"\tau_{net}",
}


def _display_number(value: float) -> str:
    magnitude = abs(value)
    if magnitude and (magnitude >= 1e6 or magnitude < 1e-4):
        return f"{value:.6g}"
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _equation_layout(
    working: str,
    *,
    result_symbol: str | None,
) -> tuple[list[str], list[str]]:
    """Separate solver-owned equation chains into symbolic and numeric rows."""
    chains = [chain.strip() for chain in working.split(r", \quad ")]
    formulas: list[str] = []
    substitutions: list[str] = []
    for chain in chains:
        parts = chain.split(" = ")
        lhs = result_symbol if len(chains) == 1 and result_symbol else parts[0].strip()
        arrow_rearrangement = len(parts) >= 3 and r"\Rightarrow" in parts[1]
        if arrow_rearrangement:
            formulas.append(f"{lhs} = {parts[2].split(r'\approx', 1)[0].strip()}")
        elif len(parts) >= 2:
            formula_rhs = parts[1].split(r"\approx", 1)[0].strip()
            formulas.append(f"{parts[0].strip()} = {formula_rhs}")
        else:
            formulas.append(chain)

        if len(parts) >= 3:
            substitution_rhs = parts[-1].split(r"\approx", 1)[0].strip()
            substitutions.append(f"{lhs} = {substitution_rhs}")
        else:
            substitutions.append(chain.split(r"\approx", 1)[0].strip())
    return formulas, substitutions


def format_direct_physics_working(verified: VerifiedMathBlock) -> str | None:
    """Five-section worked layout for a solver-verified instant reply.

    This formats the intent and the solver's exact equation chain; it never
    derives a result. The answer remains the canonical answer fence appended
    by the generic direct formatter.
    """
    intent = verified.physics_intent
    working = verified.physics_working
    if not isinstance(intent, PhysicsIntent) or not working:
        return None

    params = intent.physics_params or {}
    units = intent.physics_units or {}
    given = []
    for name, value in params.items():
        symbol = _SYMBOLS.get(name, name)
        unit = units.get(name)
        suffix = rf"\,\mathrm{{{unit}}}" if unit else ""
        given.append(rf"${symbol} = {_display_number(value)}{suffix}$")

    result_symbol = _RESULT_SYMBOLS.get(intent.physics_op or "")
    if intent.kind == "kinematics" and intent.physics_op == "speed" and "t" not in params:
        result_symbol = "v_{impact}"
    formulas, substitutions = _equation_layout(working, result_symbol=result_symbol)
    if (
        " = " not in working
        and intent.kind == "kinematics"
        and intent.physics_op
        in {
            "velocity",
            "speed",
        }
    ):
        if "t" in params:
            substitutions = [
                rf"v = {_display_number(params['v0'])} - "
                rf"{_display_number(params['g'])} \cdot {_display_number(params['t'])}"
            ]
        else:
            substitutions = [
                rf"v = \sqrt{{({_display_number(params['v0'])})^2 + 2 \cdot "
                rf"{_display_number(params['g'])} \cdot {_display_number(params.get('h0', 0.0))}}}"
            ]

    find_symbol = result_symbol or formulas[0].split(" = ", 1)[0]
    rows = ["**Given**", *given, "**Find**", f"${find_symbol}$", "**Formula**"]
    rows.extend(f"${formula}$" for formula in formulas)
    rows.append("**Substitution**")
    rows.extend(f"${substitution}$" for substitution in substitutions)
    rows.append("**Answer**")
    return "\n\n".join(rows)
