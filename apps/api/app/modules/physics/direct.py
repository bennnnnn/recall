"""Complete literal physics requests may display their existing verified result.

This grammar validates quantities and their roles; it does not solve equations
or discard extra clauses. The block carries the exact intent that was solved.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from app.models.schemas.physics import PhysicsIntent
from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES
from app.modules.physics.block import _format_visible_answer
from app.modules.physics.catalog import CATALOG, formula_spec, visible_assumptions
from app.modules.physics.extract import (
    _LENGTH_UNIT_PATTERN,
    _VELOCITY_UNIT_PATTERN,
    extract_physics_intent,
)
from app.services.solving import VerifiedPhysicsBlock

_NUMBER = r"-?(?:[0-9]{1,12}(?:\.[0-9]{1,12})?|\.[0-9]{1,12})"
_TIME = r"seconds?|s|minutes?|min|milliseconds?|ms|hours?|hr|h"
_MASS = r"kg|mg|g|lbs|lb|oz"
_ACCELERATION = r"m/s\^?2"
_ASK = r"(?:find|calculate|compute|determine|what is) (?:the|its) "
_GRAVITY = re.compile(rf"g\s*=\s*(?P<g>{_NUMBER})(?:\s+m/s\^?2)?", re.IGNORECASE)
_EXTRA_REQUEST = re.compile(
    r"\b(?:hint|air resistance|(?<!stokes )(?<!stokes' )drag|wind|"
    r"convert the answer|convert (?:it|this|that))\b"
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


def _expected_intent(text: str) -> PhysicsIntent | None:
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
    if intent.kind == "suvat":
        if intent.physics_op == "suvat_distance" or (
            intent.physics_op == "suvat_time" and "d" in (intent.physics_params or {})
        ):
            return "position_vs_time"
        return "velocity_vs_time"
    if intent.physics_op in ("velocity", "speed"):
        return "velocity_vs_time"
    return "position_vs_time"


def can_direct_physics(
    verified: VerifiedPhysicsBlock, text: str, fences: list[dict[str, Any]]
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
    if not verified.physics_working:
        return False
    fence = answering[0]
    # The legacy exact grammars remain a useful second check for their closed
    # subset. Every other physics kind is already guarded by deterministic
    # extraction plus a solver-owned canonical fence, so it can return without
    # waiting for a language model as well.
    actual = expected or extract_physics_intent(text)
    if actual is None or _EXTRA_REQUEST.search(text):
        return False
    if actual.model_dump() != intent.model_dump():
        return False
    if fence.get("type") == "answer":
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
        and fence.get("trajectory_type") == _expected_trajectory_type(actual)
    )


_SYMBOLS = {
    "angle": r"\theta",
    "mu": r"\mu",
    "h0": r"h_0",
    "v0": r"v_0",
    "d_obj": "u",
    "focal": "f",
    "delta_temp": r"\Delta T",
    "temp": "T",
    "c_heat": "c",
    "b_field": "B",
    "wire_L": "L",
    "radius_body": "R",
    "inertia": "I",
    "wavelength": r"\lambda",
    "freq": "f",
    "freq2": "f_2",
    "E_out": "E_{out}",
    "E_in": "E_{in}",
    "x1": "x_1",
    "x2": "x_2",
    "m1": "m_1",
    "m2": "m_2",
    "v1": "v_1",
    "v2": "v_2",
    "v_wave": "v",
    "tension": "T",
    "linear_density": r"\mu",
    "sound_power": "P",
    "harmonic": "n",
    "alpha": r"\alpha",
    "latent_heat": "L",
    "heat": "Q",
    "pres1": "P_1",
    "rho": r"\rho",
    "F1": "F_1",
    "A1": "A_1",
    "A2": "A_2",
    "L0": "L_0",
    "capacitance": "C",
    "intensity0": "I_0",
    "proper_time": r"\Delta t_0",
    "proper_length": "L_0",
    "work_function": r"\phi",
    "uncertainty_x": r"\Delta x",
    "quantum_n": "n",
    "temp_env": "T_C",
    "emissivity": r"\epsilon",
    "thermal_conductivity": "k",
    "viscosity": r"\eta",
    "surface_tension": r"\gamma",
    "q1": "q_1",
    "q2": "q_2",
    "omega0": r"\omega_0",
    "ang_alpha": r"\alpha",
    "theta0": r"\theta_0",
    "inertia_i": "I_i",
    "inertia_f": "I_f",
    "inertia_cm": "I_{cm}",
    "omega_i": r"\omega_i",
    "omega_f": r"\omega_f",
    "L_i": "L_i",
    "L_f": "L_f",
    "h1": "h_1",
    "h2": "h_2",
    "k": "k",
}

_FORMULA_LAW_NAMES = {spec.id: spec.law_name for spec in CATALOG.values()}
_RESULT_SYMBOLS = {spec.id: spec.result_symbol for spec in CATALOG.values()}


def _display_number(value: float) -> str:
    magnitude = abs(value)
    if magnitude and (magnitude >= 1e6 or magnitude < 1e-4):
        return f"{value:.6g}"
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _parameter_symbol(name: str) -> str:
    """Turn solver parameter names into readable mathematical symbols."""
    mapped = _SYMBOLS.get(name)
    if mapped is not None:
        return mapped
    numbered = re.fullmatch(r"([A-Za-z]+)([0-9]+)", name)
    if numbered is not None:
        stem, index = numbered.groups()
        return f"{stem}_{index}" if len(index) == 1 else f"{stem}_{{{index}}}"
    return name


def _given_unit_suffix(unit: str | None) -> str:
    if not unit:
        return ""
    if unit.lower() in {"deg", "degree", "degrees", "°"}:
        return r"^\circ"
    return rf"\,\mathrm{{{unit}}}"


def _formula_identity(formula: str) -> str:
    """Ignore presentation-only multiplication dots when comparing laws."""
    return formula.replace(r"\cdot", "").replace(" ", "")


def _result_symbol(intent: PhysicsIntent, params: dict[str, float]) -> str | None:
    """Return the quantity the solver derived, not merely its shared operation."""
    if intent.kind == "force" and intent.physics_op == "net_force":
        # F = ma uses one operation for three rearrangements. The two supplied
        # quantities identify the missing result unambiguously.
        missing = [symbol for symbol in ("F", "m", "a") if symbol not in params]
        if len(missing) == 1:
            return missing[0]
    if intent.kind == "torque" and intent.physics_op == "moment_balance" and "d2" in params:
        return "F_2"
    if intent.physics_op == "final_velocity" and params.get("elastic") == 1.0:
        return r"v_1',\ v_2'"
    chosen = _missing_result_symbol(intent.physics_op or "", params)
    if chosen is not None:
        return chosen
    return _RESULT_SYMBOLS.get(intent.physics_op or "")


# Operations that solve for whichever one of these quantities was left out.
_ONE_UNKNOWN: dict[str, tuple[tuple[str, str], ...]] = {
    "work_energy": (("W", "W_{net}"), ("m", "m"), ("v1", "v_1"), ("v2", "v_2")),
    "mechanical_energy_gravity": (("v1", "v_1"), ("h1", "h_1"), ("v2", "v_2"), ("h2", "h_2")),
    "mechanical_energy_spring": (("v1", "v_1"), ("x1", "x_1"), ("v2", "v_2"), ("x2", "x_2")),
    "torque_inertia": (("tau", r"\tau"), ("inertia", "I"), ("ang_alpha", r"\alpha")),
    "torque_angular_impulse": (
        ("tau", r"\tau"),
        ("L_i", "L_i"),
        ("L_f", "L_f"),
        ("t", r"\Delta t"),
    ),
    "angular_momentum_conservation": (
        ("inertia_i", "I_i"),
        ("omega_i", r"\omega_i"),
        ("inertia_f", "I_f"),
        ("omega_f", r"\omega_f"),
    ),
    "rolling_speed": (("v", "v"), ("omega", r"\omega"), ("r", "R")),
    "rolling_acceleration": (("a", "a"), ("ang_alpha", r"\alpha"), ("r", "R")),
    "parallel_axis": (("inertia", "I"), ("inertia_cm", "I_{cm}"), ("m", "M"), ("d", "d")),
}


def _missing_result_symbol(operation: str, params: dict[str, float]) -> str | None:
    slots = _ONE_UNKNOWN.get(operation)
    if slots is None:
        return None
    missing = [symbol for key, symbol in slots if key not in params]
    if len(missing) == 1:
        return missing[0]
    return None


def _formula_rows(intent: PhysicsIntent, formulas: list[str]) -> list[str]:
    """Name the governing law, show its base form, then any rearrangement."""
    operation = intent.physics_op or ""
    spec = formula_spec(operation)
    name = spec.law_name if spec is not None else "Physics formula"
    if operation == "final_velocity":
        if (intent.physics_params or {}).get("elastic") == 1.0:
            return [
                f"{name}:",
                r"$v_1' = \frac{(m_1-m_2)v_1 + 2m_2v_2}{m_1+m_2}$",
                r"$v_2' = \frac{(m_2-m_1)v_2 + 2m_1v_1}{m_1+m_2}$",
            ]
        return [
            f"{name}:",
            r"$m_1v_1 + m_2v_2 = (m_1+m_2)v_f$",
            r"$v_f = \frac{m_1v_1 + m_2v_2}{m_1+m_2}$",
        ]
    params = intent.physics_params or {}
    base = None if spec is None else spec.base_latex
    if operation == "work" and "angle" in params:
        base = r"W = Fd\cos\theta"
    elif operation == "power" and "angle" in params:
        base = r"P = Fv\cos\theta"
    elif operation == "magnetic_force_charge" and "angle" in params:
        base = r"F = qvB\sin\theta"
    elif operation == "magnetic_force_wire" and "angle" in params:
        base = r"F = BIL\sin\theta"
    elif operation == "magnetic_flux" and "angle" in params:
        base = r"\Phi = BA\cos\theta"
    elif operation == "doppler_frequency" and "v_obs" in params:
        base = r"f' = f\frac{v+v_o}{v-v_s}"
    elif operation == "bernoulli_pressure" and "h1" in params:
        base = (
            r"P_1 + \frac{1}{2}\rho v_1^2 + \rho gh_1 = "
            r"P_2 + \frac{1}{2}\rho v_2^2 + \rho gh_2"
        )
    if operation == "resonance_frequency":
        # A pipe closed at one end has a 4L fundamental; an open pipe or a
        # string has 2L. Show the actual universal law for the apparatus rather
        # than exposing the solver's internal denominator selector as "k".
        denominator = 4 if (intent.physics_params or {}).get("mode_factor") == 4 else 2
        base = rf"f_n = \frac{{nv}}{{{denominator}L}}"
    if operation == "laplace_pressure":
        numerator = 4 if (intent.physics_params or {}).get("mode_factor") == 4 else 2
        base = rf"\Delta P = \frac{{{numerator}\gamma}}{{r}}"
    rows = [f"{name}:"]
    if base is None:
        rows.extend(f"${formula}$" for formula in formulas)
        return rows

    rows.append(f"${base}$")
    base_lhs = base.split(" = ", 1)[0].strip()
    for formula in formulas:
        formula_lhs = formula.split(" = ", 1)[0].strip()
        if _formula_identity(formula) == _formula_identity(base):
            continue
        if formula_lhs == base_lhs:
            rows.append("Equivalent form for the given quantities:")
        else:
            rows.append(f"Rearranged for ${formula_lhs}$:")
        rows.append(f"${formula}$")
    return rows


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
    return (
        [_format_visible_answer(formula) for formula in formulas],
        [_format_visible_answer(substitution) for substitution in substitutions],
    )


def format_direct_physics_working(verified: VerifiedPhysicsBlock) -> str | None:
    """Five-section worked layout for a solver-verified instant reply.

    This formats the intent and the solver's exact equation chain; it never
    derives a result. The answer remains the canonical answer fence appended
    by the generic direct formatter.
    """
    intent = verified.physics_intent
    working = verified.physics_working
    if intent is None or not working:
        return None

    params = intent.physics_params or {}
    units = intent.physics_units or {}
    given_rows: list[str] = []
    for name, value in params.items():
        if name in {"elastic", "mode_factor"}:
            continue
        symbol = _parameter_symbol(name)
        if intent.physics_op == "carnot_efficiency" and name == "temp":
            symbol = "T_H"
        if intent.physics_op == "beat_frequency" and name == "freq":
            symbol = "f_1"
        suffix = _given_unit_suffix(units.get(name))
        given_rows.append(rf"${symbol} = {_display_number(value)}{suffix}$")

    result_symbol = _result_symbol(intent, params)
    if intent.kind == "kinematics" and intent.physics_op == "speed" and "t" not in params:
        result_symbol = "v_{impact}"
    formulas, substitutions = _equation_layout(working, result_symbol=result_symbol)
    if intent.physics_op in {"average_speed", "rate_speed"} and {"d", "t"} <= params.keys():
        distance_unit = _given_unit_suffix(units.get("d"))
        time_unit = _given_unit_suffix(units.get("t"))
        substitutions = [
            rf"v = \frac{{{_display_number(params['d'])}{distance_unit}}}"
            rf"{{{_display_number(params['t'])}{time_unit}}}"
        ]
    elif intent.physics_op == "rate_distance" and {"v", "t"} <= params.keys():
        speed_unit = _given_unit_suffix(units.get("v"))
        time_unit = _given_unit_suffix(units.get("t"))
        substitutions = [
            rf"d = {_display_number(params['v'])}{speed_unit} \cdot "
            rf"{_display_number(params['t'])}{time_unit}"
        ]
    elif intent.physics_op == "rate_time" and {"d", "v"} <= params.keys():
        distance_unit = _given_unit_suffix(units.get("d"))
        speed_unit = _given_unit_suffix(units.get("v"))
        substitutions = [
            rf"t = \frac{{{_display_number(params['d'])}{distance_unit}}}"
            rf"{{{_display_number(params['v'])}{speed_unit}}}"
        ]
    if intent.physics_op == "final_velocity" and {"m1", "m2", "v1", "v2"} <= params.keys():
        m1 = _display_number(params["m1"])
        m2 = _display_number(params["m2"])
        v1 = _display_number(params["v1"])
        v2 = _display_number(params["v2"])
        if params.get("elastic") == 1.0:
            substitutions = [
                rf"v_1' = \frac{{({m1}-{m2})\cdot {v1} + 2\cdot {m2}\cdot {v2}}}"
                rf"{{{m1}+{m2}}}",
                rf"v_2' = \frac{{({m2}-{m1})\cdot {v2} + 2\cdot {m1}\cdot {v1}}}"
                rf"{{{m1}+{m2}}}",
            ]
        else:
            substitutions = [rf"v_f = \frac{{{m1}\cdot {v1} + {m2}\cdot {v2}}}{{{m1}+{m2}}}"]
    if intent.kind == "projectile" and intent.physics_op == "max_height":
        needed = {"v0", "angle", "g"}
        if needed <= params.keys():
            h0 = _display_number(params.get("h0", 0.0))
            substitutions = [
                rf"H_{{max}} = {h0} + "
                rf"\frac{{{_display_number(params['v0'])}^2 "
                rf"\sin^2({_display_number(params['angle'])}^\circ)}}"
                rf"{{2 \cdot {_display_number(params['g'])}}}"
            ]
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
    rows = ["**Given**", *given_rows, "**Find**", f"${find_symbol}$", "**Formula**"]
    rows.extend(_formula_rows(intent, formulas))
    spec = formula_spec(intent.physics_op or "")
    if spec is not None:
        rows.extend(
            f"Assumption: {assumption}." for assumption in visible_assumptions(spec, params)
        )
    rows.append("**Substitution**")
    rows.extend(f"${substitution}$" for substitution in substitutions)
    rows.append("**Answer**")
    return "\n\n".join(rows)


def _solver_fences(verified: VerifiedPhysicsBlock) -> list[dict[str, Any]]:
    fences: list[dict[str, Any]] = []
    for fence in (verified.canonical_fence, *verified.canonical_fences):
        if fence is not None and fence not in fences:
            fences.append(fence)
    return fences


def maybe_direct_physics_reply(
    verified: VerifiedPhysicsBlock | None,
    user_text: str,
    *,
    has_image_attachment: bool = False,
) -> str | None:
    """Render a complete physics reply from solver-owned data only."""
    if verified is None or has_image_attachment:
        return None
    fences = _solver_fences(verified)
    if not can_direct_physics(verified, user_text, fences):
        return None
    working = format_direct_physics_working(verified)
    if working is None:
        return None
    answer = (verified.display_answer or verified.canonical_answer or "").strip()
    if not answer:
        return None
    parts = [working, f"```answer\n{answer}\n```"]
    for fence in fences:
        fence_type = fence.get("type")
        if fence_type == "answer":
            continue
        language = "simulation" if fence_type in SIMULATION_SPEC_TYPES else "graph"
        parts.append(f"```{language}\n{json.dumps(fence, separators=(',', ':'))}\n```")
    reply = "\n\n".join(parts) + "\n"
    intent = verified.physics_intent
    if (
        intent is not None
        and intent.kind == "kinematics"
        and intent.physics_op
        in {
            "velocity",
            "acceleration",
        }
    ):
        return f"Upward is positive.\n\n{reply}"
    return reply
