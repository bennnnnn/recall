"""Thermal extractors: heat, expansion, phase change, gas laws, efficiency."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _MASS_UNITS,
    _NUMBER,
    _find_value_with_specific_unit,
    _has_cue,
    _strip_param_assignments,
)
from app.modules.physics.extractors.fluid_readings import _AREA_PATTERN
from app.modules.physics.extractors.school_extensions import blocks_thermal
from app.modules.physics.extractors.thermal_readings import (
    _CELSIUS_PATTERN,
    _KELVIN_PATTERN,
    _REJECTED_WORDS,
    _SPECIFIC_HEAT_UNIT,
    _SUPPLIED_WORDS,
    _TEMPERATURE_SPAN,
    _WATER_SPECIFIC_HEAT,
    _WORK_WORDS,
    _efficiency_intent,
    _nearest_labeled_energy,
    _reservoir_temperatures,
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

    if "carnot" in lower:
        reservoirs = _reservoir_temperatures(cleaned)
        if reservoirs is None:
            return None
        (hot, hot_unit), (cold, cold_unit) = reservoirs
        return PhysicsIntent(
            kind="thermal",
            physics_op="carnot_efficiency",
            physics_params={"temp": hot, "temp_env": cold},
            physics_units={"temp": hot_unit, "temp_env": cold_unit},
            operation="solve",
        )

    if "entropy" in lower:
        heat = _find_value_with_specific_unit(
            cleaned, r"kilojoules?|joules?|kJ|J", ("heat", "energy")
        )
        temp = _temperature_value(cleaned, ("temperature", "at"))
        if heat is None or temp is None or temp[1] != "K":
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="entropy_change",
            physics_params={"heat": heat[0], "temp": temp[0]},
            physics_units={"heat": heat[1] or "J", "temp": "K"},
            operation="solve",
        )

    if "heat conduction" in lower or "thermal conductivity" in lower:
        conductivity = _find_value_with_specific_unit(
            cleaned,
            r"W/m/K|W/\(m\s*K\)|watts?\s+per\s+met(?:er|re)\s+per\s+kelvin",
            ("thermal conductivity", "conductivity"),
        )
        area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN, ("area",))
        thickness = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("thickness", "length"), require_keyword=True
        )
        rise = _temperature_change(cleaned, ("temperature difference", "difference", "delta t"))
        if conductivity is None or area is None or thickness is None or rise is None:
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="heat_conduction_rate",
            physics_params={
                "thermal_conductivity": conductivity[0],
                "area": area[0],
                "delta_temp": rise[0],
                "L": thickness[0],
            },
            physics_units={
                "thermal_conductivity": conductivity[1] or "W/m/K",
                "area": area[1] or "m^2",
                "delta_temp": "K",
                "L": thickness[1] or "m",
            },
            operation="solve",
        )

    # --- linear thermal expansion: dL = alpha L0 dT --------------------
    if "expansion" in lower:
        length = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("rod", "wire", "length", "long")
        )
        alpha_match = re.search(
            rf"(?:coefficient(?:\s+of\s+linear\s+expansion)?|alpha|\u03b1)\s*"
            rf"(?:of|is|=|:)?\s*({_NUMBER})\s*(1/K|/K|K\^?-?1|1/°C|/°C)",
            cleaned,
            re.IGNORECASE,
        )
        rise = _temperature_change(cleaned, ("heated by", "temperature change", "change", "by"))
        if length is None or alpha_match is None or rise is None:
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="linear_expansion",
            physics_params={
                "L0": length[0],
                "alpha": float(alpha_match.group(1)),
                "delta_temp": rise[0],
            },
            physics_units={
                "L0": length[1] or "m",
                "alpha": alpha_match.group(2),
                "delta_temp": "K",
            },
            operation="solve",
        )

    # --- phase change: Q = m L -----------------------------------------
    if "latent heat" in lower:
        mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "of"))
        latent = _find_value_with_specific_unit(
            cleaned,
            r"J/kg|kJ/kg|joules?\s+per\s+kilogram|kilojoules?\s+per\s+kilogram",
            ("latent heat",),
        )
        if mass is None or latent is None:
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="latent_heat",
            physics_params={"m": mass[0], "latent_heat": latent[0]},
            physics_units={"m": mass[1] or "kg", "latent_heat": latent[1] or "J/kg"},
            operation="solve",
        )

    # --- first law: dU = Q - W (work done by the system is positive) ----
    if "first law" in lower or "internal energy" in lower:
        heat_match = re.search(
            rf"(?:heat|energy)\s+(?:added|absorbed|supplied)\D{{0,20}}?({_NUMBER})\s*"
            r"(kilojoules?|joules?|kJ|J)",
            cleaned,
            re.IGNORECASE,
        )
        work_match = re.search(
            rf"work\s+(?:done\s+)?by\s+(?:the\s+)?(?:system|gas)\D{{0,20}}?({_NUMBER})\s*"
            r"(kilojoules?|joules?|kJ|J)",
            cleaned,
            re.IGNORECASE,
        )
        if heat_match is None or work_match is None:
            # Refuse ambiguous sign conventions such as bare "work = 200 J".
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="first_law_internal_energy",
            physics_params={"heat": float(heat_match.group(1)), "W": float(work_match.group(1))},
            physics_units={"heat": heat_match.group(2), "W": work_match.group(2)},
            operation="solve",
        )

    # --- efficiency: only from two energies -----------------------------
    if "efficiency" in lower:
        if not any(word in lower for word in ("engine", "thermal", "heat")):
            # Machine/mechanical efficiency is handled by the energy
            # extractor, which runs later in the registry.
            return None
        # Two temperatures is a Carnot question. Two unlabeled energies are
        # not sorted into work and heat: that verifies the smaller number as work.
        return _efficiency_intent(
            _nearest_labeled_energy(cleaned, _WORK_WORDS),
            _nearest_labeled_energy(cleaned, _SUPPLIED_WORDS),
            _nearest_labeled_energy(cleaned, _REJECTED_WORDS),
        )

    # --- ideal gas: P V = n R T -----------------------------------------
    moles = _find_value_with_specific_unit(cleaned, r"mol|moles?")
    if moles is not None or "ideal gas" in lower:
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

    # --- Q = m c dT ------------------------------------------------------
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
