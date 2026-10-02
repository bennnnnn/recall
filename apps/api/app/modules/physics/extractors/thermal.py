"""Thermal extractors: heat, expansion, phase change, gas laws, efficiency."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _MASS_UNITS,
    _NUMBER,
    _find_value_with_specific_unit,
    _has_cue,
    _strip_param_assignments,
)
from app.modules.physics.extractors.school_extensions import blocks_thermal
from app.modules.physics.extractors.thermal_laws import NAMED_THERMAL_LAWS
from app.modules.physics.extractors.thermal_readings import (
    _CELSIUS_PATTERN,
    _KELVIN_PATTERN,
    _SPECIFIC_HEAT_UNIT,
    _TEMPERATURE_SPAN,
    _WATER_SPECIFIC_HEAT,
    _temperature_change,
    _temperature_value,
)
from app.services.text_match import has_equation

_THERMAL_CUES = (
    "specific heat",
    "heat capacity",
    "ideal gas",
    "gas constant",
    "thermal expansion",
    "linear expansion",
    "coefficient of linear expansion",
    "latent heat",
    "first law of thermodynamics",
    "internal energy",
    "carnot",
    "entropy",
    "heat conduction",
    "thermal conductivity",
)

_THERMAL_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\b(?:heat|warm|cool)\w*\b.{{0,80}}?\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN}).{{0,80}}?\b(?:heat|warm|cool)\w*\b",
        re.IGNORECASE,
    ),
    re.compile(r"\befficiency\b.{0,80}?\d\s*(?:J|joules?|kJ|kilojoules?)\b", re.IGNORECASE),
    re.compile(r"\d\s*(?:J|joules?|kJ|kilojoules?)\b.{0,80}?\befficiency\b", re.IGNORECASE),
    # "the pressure of 2 moles of gas at 300 K" names no thermal word at all -
    # a mole count beside a temperature is the signature itself.
    re.compile(
        rf"\d\s*mol(?:e|es)?\b.{{0,80}}?\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN}).{{0,80}}?\d\s*mol(?:e|es)?\b",
        re.IGNORECASE,
    ),
)


def _extract_thermal_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _THERMAL_CUES, _THERMAL_CUE_RES):
        return None
    if blocks_thermal(cleaned):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    for names, law in NAMED_THERMAL_LAWS:
        if any(name in lower for name in names):
            return law(cleaned)

    # A stated amount of gas is PV = nRT; anything else left is Q = mc dT.
    moles = _find_value_with_specific_unit(cleaned, r"mol|moles?")
    if moles is not None or "ideal gas" in lower:
        return _ideal_gas(cleaned, moles)
    return _heat_energy(cleaned)


def _ideal_gas(cleaned: str, moles: tuple[float, str] | None) -> PhysicsIntent | None:
    """PV = nRT for the pressure, from moles, a volume and an absolute temperature."""
    volume = _find_value_with_specific_unit(cleaned, r"m\^?3|cm\^?3|litres?|liters?|l|ml")
    temp = _temperature_value(cleaned, ("temperature", "at"))
    if moles is None or volume is None or temp is None:
        return None
    if temp[1] != "K":
        # PV = nRT needs an absolute temperature. Celsius would be wrong by
        # 273 and look plausible.
        return None
    return PhysicsIntent(
        kind="thermal",
        physics_op="ideal_gas_pressure",
        physics_params={"moles": moles[0], "volume": volume[0], "temp": temp[0]},
        physics_units={
            "moles": "mol",
            "volume": volume[1] or "m^3",
            "temp": "K",
        },
        operation="solve",
    )


def _heat_energy(cleaned: str) -> PhysicsIntent | None:
    """Q = mc dT, from a stated change or two readings, and a stated or water's c."""
    lower = cleaned.lower()
    mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "of"))
    readings = _TEMPERATURE_SPAN.search(cleaned)
    rise = None if readings else _temperature_change(cleaned, ("by", "rise", "raise", "change"))
    if rise is None and readings is None:
        # A temperature *difference* is the same number in kelvin and celsius,
        # so a bare "by 10 degrees" is unambiguous here in a way an absolute
        # "at 300 degrees" is not. Only the interval may be loose.
        bare = re.search(
            rf"(?:by|rises?|raise[sd]?|warms?|cools?)\s+(?:by\s+)?({_NUMBER})\s*"
            r"(?:degrees?|deg|\u00b0)(?![A-Za-z0-9])",
            cleaned,
            re.IGNORECASE,
        )
        if bare is not None:
            rise = (float(bare.group(1)), "K")
    if mass is None or (rise is None and readings is None):
        return None
    capacity = _find_value_with_specific_unit(
        cleaned, _SPECIFIC_HEAT_UNIT, ("specific heat", "capacity", "c =", "c is")
    )
    if capacity is not None:
        c_value = capacity[0]
        c_unit = "kJ/kg/K" if capacity[1].lstrip().lower().startswith("k") else "J/kg/K"
    elif "water" in lower:
        c_value, c_unit = _WATER_SPECIFIC_HEAT, "J/kg/K"
    else:
        # No capacity and no named substance: the answer would be a guess.
        return None
    params = {"m": mass[0], "c_heat": c_value}
    units = {"m": mass[1] or "kg", "c_heat": c_unit}
    if readings is not None:
        scale = readings.group(4)
        first_scale = readings.group(2) or scale
        params.update(temp_initial=float(readings.group(1)), temp_final=float(readings.group(3)))
        units.update(
            temp_initial=_temperature_unit(first_scale), temp_final=_temperature_unit(scale)
        )
    elif rise is not None:
        # A temperature *difference* is the same number in kelvin and celsius,
        # so this one does not need the scale an absolute reading does.
        params["delta_temp"] = rise[0]
        units["delta_temp"] = "K"
    return PhysicsIntent(
        kind="thermal",
        physics_op="heat_energy",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


def _temperature_unit(scale: str) -> str:
    return "K" if scale.strip().upper() == "K" else "degC"
