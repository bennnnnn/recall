"""Rotational kinematics, rolling, and the parallel-axis theorem.

The patterns are explicit on purpose. A nearby sentence that only shares a
word such as "angular" must keep the older θ/t and L = Iω operations.
"""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _find_value_with_specific_unit,
)
from app.modules.physics.extractors.rotation import _INERTIA_PATTERN

_OMEGA_UNIT = r"rad(?:ians?)?\s*/\s*s(?:ec(?:ond)?s?)?(?!\s*(?:\^?\s*2|squared))"
_ALPHA_UNIT = r"rad(?:ians?)?\s*/\s*s(?:ec(?:ond)?s?)?\s*(?:\^?\s*2|squared)"
_TIME_UNIT = r"seconds?|secs?|sec|s"
_TORQUE_UNIT = r"(?:N|newtons?)\s*(?:[·*]\s*)?(?:m|met(?:er|re)s?)"
_CLAIM_RE = re.compile(
    r"parallel[- ]axis|without slipping|angular momentum is conserved|"
    r"\bisolated\b.*\bangular momentum\b|\bangular momentum\b.*\bisolated\b|"
    r"rad(?:ians?)?\s*/\s*s(?:ec(?:ond)?s?)?\s*(?:\^?\s*2|squared)",
    re.IGNORECASE,
)


def claims_rotational_dynamics(text: str) -> bool:
    lower = text.lower()
    if _CLAIM_RE.search(text) is not None:
        return True
    if "torque" in lower and "angular momentum" in lower and re.search(r"\bfind\b", lower):
        return True
    if re.search(r"\b(?:conserved|isolated)\b", lower) and lower.count("inertia") >= 2:
        return True
    return "torque" in lower and "moment of inertia" in lower and "angular acceleration" in lower


def extract_rotational_dynamics(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if "parallel-axis" in lower or "parallel axis" in lower:
        return _parallel_axis(cleaned)
    if "without slipping" in lower or "rolls without" in lower:
        return _rolling(cleaned)
    if re.search(r"\b(?:conserved|isolated)\b", lower) and (
        "angular momentum" in lower or lower.count("inertia") >= 2
    ):
        return _angular_momentum(cleaned)
    if "angular momentum" in lower and "torque" in lower:
        return _angular_impulse(cleaned)
    if "torque" in lower and (
        "moment of inertia" in lower or re.search(_INERTIA_PATTERN, cleaned, re.I)
    ):
        if "angular acceleration" in lower or re.search(_ALPHA_UNIT, cleaned, re.I):
            return _torque_inertia(cleaned)
    if re.search(_ALPHA_UNIT, cleaned, re.I) or "angular acceleration" in lower:
        return _kinematics(cleaned)
    return None


def _intent(operation: str, params: dict[str, float], units: dict[str, str]) -> PhysicsIntent:
    return PhysicsIntent(
        kind="rotation",
        physics_op=operation,  # type: ignore[arg-type]
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


def _first(text: str, label: str, unit: str) -> tuple[float, str] | None:
    match = re.search(
        rf"\b(?:{label})(?:\s+of)?\s+({_NUMBER})\s*({unit})\b",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return float(match.group(1)), match.group(2)


def _omega_pair(text: str) -> tuple[tuple[float, str], tuple[float, str]] | None:
    match = re.search(
        rf"\bfrom\s+({_NUMBER})\s*({_OMEGA_UNIT})\s+to\s+({_NUMBER})\s*({_OMEGA_UNIT})\b",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return (float(match.group(1)), match.group(2)), (float(match.group(3)), match.group(4))


def _time(text: str) -> tuple[float, str] | None:
    match = re.search(rf"\b(?:after|in)\s+({_NUMBER})\s*({_TIME_UNIT})\b", text, re.IGNORECASE)
    if match is None:
        return None
    return float(match.group(1)), match.group(2)


def _alpha(text: str) -> tuple[float, str] | None:
    found = _first(text, r"angular acceleration", _ALPHA_UNIT)
    if found is not None:
        return found
    match = re.search(rf"({_NUMBER})\s*({_ALPHA_UNIT})\b", text, re.IGNORECASE)
    if match is None:
        return None
    return float(match.group(1)), "rad/s^2"


def _from_rest(text: str) -> bool:
    return (
        re.search(r"\b(?:from rest|starts at rest|starts from rest)\b", text, re.IGNORECASE)
        is not None
    )


def _kinematics(cleaned: str) -> PhysicsIntent | None:
    params: dict[str, float] = {}
    units: dict[str, str] = {}
    if _from_rest(cleaned):
        params["omega0"] = 0.0
        units["omega0"] = "rad/s"
    pair = _omega_pair(cleaned)
    if pair is not None:
        params["omega0"], units["omega0"] = pair[0]
        params["omega"], units["omega"] = pair[1]
    initial = _first(cleaned, r"initial angular (?:velocity|speed)", _OMEGA_UNIT)
    final = _first(cleaned, r"(?:final )?angular (?:velocity|speed)", _OMEGA_UNIT)
    if initial is not None:
        params["omega0"], units["omega0"] = initial
    elif (
        final is not None
        and "omega" not in params
        and not re.search(r"\bfind\b.{0,40}?\bangular (?:velocity|speed)\b", cleaned, re.IGNORECASE)
    ):
        params["omega0"], units["omega0"] = final
    alpha = _alpha(cleaned)
    if alpha is not None:
        params["ang_alpha"] = alpha[0]
        units["ang_alpha"] = "rad/s^2"
    elapsed = _time(cleaned)
    if elapsed is not None:
        params["t"], units["t"] = elapsed
    angle = _first(cleaned, r"angular displacement|angle", r"radians?|rad")
    if angle is not None:
        params["theta"], units["theta"] = angle[0], "rad"
    lower = cleaned.lower()
    asks_omega = (
        re.search(r"\b(?:find|what is)\b.{0,40}?\bangular (?:velocity|speed)\b", lower)
        and "initial" not in lower.split("find", 1)[-1][:40]
    )
    asks_theta = (
        re.search(r"\b(?:find|what is)\b.{0,40}?\bangular displacement\b", lower) is not None
    )
    asks_alpha = (
        re.search(r"\b(?:find|what is)\b.{0,40}?\bangular acceleration\b", lower) is not None
    )
    if asks_alpha:
        params.pop("ang_alpha", None)
        if {"omega", "omega0", "t"} <= params.keys() or {
            "omega",
            "omega0",
            "theta",
        } <= params.keys():
            return _intent("rotational_alpha", params, units)
        return None
    if asks_theta:
        params.pop("theta", None)
        if {"omega0", "ang_alpha", "t"} <= params.keys() or {
            "omega",
            "omega0",
            "ang_alpha",
        } <= params.keys():
            return _intent("rotational_theta", params, units)
        return None
    if asks_omega or (
        "ang_alpha" in params and "omega0" in params and ("t" in params or "theta" in params)
    ):
        params.pop("omega", None)
        if {"omega0", "ang_alpha"} <= params.keys() and ("t" in params or "theta" in params):
            return _intent("rotational_omega", params, units)
    return None


def _torque_value(text: str) -> float | None:
    match = re.search(rf"({_NUMBER})\s*{_TORQUE_UNIT}(?![A-Za-z0-9/^])", text, re.IGNORECASE)
    if match is None:
        return None
    return float(match.group(1))


def _inertia_value(text: str) -> float | None:
    found = _find_value_with_specific_unit(text, _INERTIA_PATTERN)
    if found is None:
        return None
    return found[0]


_MASS_NOT_INERTIA_RE = re.compile(
    rf"({_NUMBER})\s*(kg|g|mg)\b(?!\s*[*·]?\s*m(?:\s*\^?\s*2|\s+squared)\b)",
    re.IGNORECASE,
)


def _mass_not_inertia(text: str) -> tuple[float, str] | None:
    """A mass in kg, g, or mg that is not the number in front of kg·m².

    "center of mass" contains the word mass, and "2 kg m^2" is an inertia, so
    a keyword search for mass would bind the wrong quantity.
    """
    match = _MASS_NOT_INERTIA_RE.search(text)
    if match is None:
        return None
    return float(match.group(1)), match.group(2)


def _torque_inertia(cleaned: str) -> PhysicsIntent | None:
    params: dict[str, float] = {}
    units: dict[str, str] = {}
    torque = _torque_value(cleaned)
    inertia = _inertia_value(cleaned)
    alpha = _alpha(cleaned)
    if torque is not None:
        params["tau"] = torque
        units["tau"] = "N*m"
    if inertia is not None:
        params["inertia"] = inertia
        units["inertia"] = "kg*m^2"
    if alpha is not None:
        params["ang_alpha"] = alpha[0]
        units["ang_alpha"] = "rad/s^2"
    lower = cleaned.lower()
    if re.search(r"\bfind\b.{0,40}?\bangular acceleration\b", lower):
        params.pop("ang_alpha", None)
        units.pop("ang_alpha", None)
    elif re.search(r"\bfind\b.{0,30}?\btorque\b", lower):
        params.pop("tau", None)
        units.pop("tau", None)
    elif re.search(r"\bfind\b.{0,40}?\bmoment of inertia\b", lower):
        params.pop("inertia", None)
        units.pop("inertia", None)
    else:
        return None
    if len({"tau", "inertia", "ang_alpha"} - params.keys()) != 1:
        return None
    return _intent("torque_inertia", params, units)


def _angular_values(text: str) -> list[float]:
    return [
        float(match.group(1))
        for match in re.finditer(
            rf"({_NUMBER})\s*(?:kg\s*m\^?2\s*/\s*s|kg\*m\^?2/s)",
            text,
            re.IGNORECASE,
        )
    ]


def _angular_impulse(cleaned: str) -> PhysicsIntent | None:
    values = _angular_values(cleaned)
    pair = re.search(
        rf"\bfrom\s+({_NUMBER})\s+to\s+({_NUMBER})\s*(?:kg\s*m\^?2\s*/\s*s|kg\*m\^?2/s)",
        cleaned,
        re.IGNORECASE,
    )
    params: dict[str, float] = {}
    units: dict[str, str] = {}
    if pair is not None:
        params["L_i"] = float(pair.group(1))
        params["L_f"] = float(pair.group(2))
        units["L_i"] = "kg*m^2/s"
        units["L_f"] = "kg*m^2/s"
    elif len(values) >= 2:
        params["L_i"], params["L_f"] = values[0], values[1]
        units["L_i"] = units["L_f"] = "kg*m^2/s"
    elapsed = _time(cleaned)
    if elapsed is not None:
        params["t"], units["t"] = elapsed
    torque = _torque_value(cleaned)
    if torque is not None and not re.search(r"\bfind\b.{0,30}?\btorque\b", cleaned, re.I):
        params["tau"] = torque
        units["tau"] = "N*m"
    if re.search(r"\bfind\b.{0,30}?\btorque\b", cleaned, re.I):
        params.pop("tau", None)
    elif re.search(r"\bfind\b.{0,40}?\btime\b", cleaned, re.I):
        params.pop("t", None)
    else:
        return None
    if len({"tau", "L_i", "L_f", "t"} - params.keys()) != 1:
        return None
    return _intent("torque_angular_impulse", params, units)


def _angular_momentum(cleaned: str) -> PhysicsIntent | None:
    inertias = [
        float(match.group(1))
        for match in re.finditer(rf"({_NUMBER})\s*(?:{_INERTIA_PATTERN})", cleaned, re.IGNORECASE)
    ]
    omegas = [
        float(match.group(1))
        for match in re.finditer(rf"({_NUMBER})\s*(?:{_OMEGA_UNIT})\b", cleaned, re.IGNORECASE)
    ]
    if len(inertias) < 1 or len(omegas) < 1:
        return None
    params: dict[str, float] = {}
    units: dict[str, str] = {}
    if len(inertias) >= 2:
        params["inertia_i"], params["inertia_f"] = inertias[0], inertias[1]
    else:
        params["inertia_i"] = inertias[0]
    units["inertia_i"] = "kg*m^2"
    if "inertia_f" in params:
        units["inertia_f"] = "kg*m^2"
    if len(omegas) >= 2:
        params["omega_i"], params["omega_f"] = omegas[0], omegas[1]
        units["omega_i"] = units["omega_f"] = "rad/s"
    else:
        params["omega_i"] = omegas[0]
        units["omega_i"] = "rad/s"
    lower = cleaned.lower()
    if re.search(r"\bfind\b.{0,40}?\b(?:final )?angular (?:velocity|speed)\b", lower):
        params.pop("omega_f", None)
        units.pop("omega_f", None)
    elif re.search(r"\bfind\b.{0,40}?\bfinal moment of inertia\b", lower):
        params.pop("inertia_f", None)
    else:
        # The usual skater question names the new inertia and asks for the new spin.
        params.pop("omega_f", None)
        units.pop("omega_f", None)
    if len({"inertia_i", "omega_i", "inertia_f", "omega_f"} - params.keys()) != 1:
        return None
    return _intent("angular_momentum_conservation", params, units)


def _rolling(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    radius = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("radius", "radii"), require_keyword=True
    )
    speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
    omega = _first(cleaned, r"angular (?:velocity|speed)", _OMEGA_UNIT)
    if omega is None:
        match = re.search(rf"({_NUMBER})\s*({_OMEGA_UNIT})\b", cleaned, re.IGNORECASE)
        if match is not None and not re.search(
            r"\bfind\b.{0,40}?\bangular (?:velocity|speed)\b", lower
        ):
            omega = (float(match.group(1)), "rad/s")
    alpha = _alpha(cleaned)
    linear_a = _find_value_with_specific_unit(cleaned, r"m/s\^?2|m/s2")
    params: dict[str, float] = {}
    units: dict[str, str] = {}
    if radius is not None:
        params["r"], units["r"] = radius
    if "kinetic energy" in lower or "total kinetic" in lower:
        mass = _mass_not_inertia(cleaned)
        inertia = _inertia_value(cleaned)
        if mass is None or inertia is None:
            return None
        params["m"], units["m"] = mass
        params["inertia"] = inertia
        units["inertia"] = "kg*m^2"
        if speed is not None and not re.search(r"\bfind\b.{0,20}?\bspeed\b", lower):
            params["v"], units["v"] = speed
        if omega is not None:
            params["omega"], units["omega"] = omega[0], "rad/s"
        if "v" not in params and "omega" not in params:
            return None
        if ("v" not in params or "omega" not in params) and "r" not in params:
            return None
        return _intent("rolling_kinetic_energy", params, units)
    if re.search(r"\bfind\b.{0,40}?\bangular acceleration\b", lower) or (
        alpha is None and linear_a is not None and "acceleration" in lower
    ):
        if linear_a is not None:
            params["a"], units["a"] = linear_a
        if radius is None:
            return None
        return _intent("rolling_acceleration", params, units)
    if alpha is not None and re.search(r"\bfind\b.{0,30}?\bacceleration\b", lower):
        params["ang_alpha"] = alpha[0]
        units["ang_alpha"] = "rad/s^2"
        if radius is None:
            return None
        return _intent("rolling_acceleration", params, units)
    if re.search(r"\bfind\b.{0,40}?\bangular (?:velocity|speed)\b", lower):
        if speed is not None:
            params["v"], units["v"] = speed
        if "r" not in params or "v" not in params:
            return None
        return _intent("rolling_speed", params, units)
    if re.search(r"\bfind\b.{0,30}?\b(?:speed|velocity)\b", lower):
        if omega is not None:
            params["omega"], units["omega"] = omega[0], "rad/s"
        if "r" not in params or "omega" not in params:
            return None
        return _intent("rolling_speed", params, units)
    return None


def _parallel_axis(cleaned: str) -> PhysicsIntent | None:
    mass = _mass_not_inertia(cleaned)
    center = _find_value_with_specific_unit(
        cleaned,
        _INERTIA_PATTERN,
        ("center of mass", "centre of mass", "cm"),
        require_keyword=True,
    )
    distance = _find_value_with_specific_unit(
        cleaned,
        _LENGTH_UNIT_PATTERN,
        ("away", "distance", "axis"),
        require_keyword=True,
    )
    if center is None or mass is None or distance is None:
        return None
    if not re.search(r"\bfind\b.{0,40}?\bmoment of inertia\b", cleaned, re.IGNORECASE):
        return None
    return _intent(
        "parallel_axis",
        {"inertia_cm": center[0], "m": mass[0], "d": distance[0]},
        {"inertia_cm": "kg*m^2", "m": mass[1] or "kg", "d": distance[1] or "m"},
    )
