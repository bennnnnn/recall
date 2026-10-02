"""Relativity, radiation, decay and mass-energy readers for modern-physics questions."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _MASS_UNITS,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _find_value_with_specific_unit,
)
from app.modules.physics.extractors.fluid_readings import _AREA_PATTERN
from app.modules.physics.extractors.thermal_readings import _temperature_value

_HALF_LIFE_COUNT_RE = re.compile(rf"({_NUMBER})\s*half[- ]li(?:ves|fe)", re.IGNORECASE)

_DECAY_TIME_UNITS = (
    r"seconds?|secs?|s|minutes?|mins?|min|hours?|hrs?|hr|days?|weeks?|months?|years?|yr"
)


def _relativistic_speed(cleaned: str) -> tuple[float, str] | None:
    """A stated speed, or a fraction of c ("0.8c")."""
    speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
    if speed is not None:
        return speed
    fraction = re.search(rf"({_NUMBER})\s*c\b", cleaned, re.IGNORECASE)
    if fraction is not None:
        return float(fraction.group(1)) * 299792458.0, "m/s"
    return None


def _relativity(cleaned: str) -> PhysicsIntent | None:
    """A Lorentz factor, a dilated time or a contracted length."""
    lower = cleaned.lower()
    speed = _relativistic_speed(cleaned)
    if speed is None:
        return None
    rel_params: dict[str, float] = {"v": speed[0]}
    rel_units: dict[str, str] = {"v": speed[1] or "m/s"}
    op: Literal["lorentz_factor", "time_dilation", "length_contraction"]
    if "time dilation" in lower:
        proper = _find_value_with_specific_unit(
            cleaned, _DECAY_TIME_UNITS, ("proper time", "rest time", "clock")
        )
        if proper is None:
            return None
        rel_params["proper_time"], rel_units["proper_time"] = proper[0], proper[1] or "s"
        op = "time_dilation"
    elif "length contraction" in lower:
        proper_length = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("proper length", "rest length")
        )
        if proper_length is None:
            return None
        rel_params["proper_length"], rel_units["proper_length"] = (
            proper_length[0],
            proper_length[1] or "m",
        )
        op = "length_contraction"
    else:
        op = "lorentz_factor"
    return PhysicsIntent(
        kind="modern",
        physics_op=op,
        physics_params=rel_params,
        physics_units=rel_units,
        operation="solve",
    )


def _wien(cleaned: str) -> PhysicsIntent | None:
    """Wien's peak wavelength at a temperature in kelvin."""
    temp = _temperature_value(cleaned, ("temperature", "at", "blackbody"))
    if temp is None or temp[1] != "K":
        return None
    return PhysicsIntent(
        kind="modern",
        physics_op="wien_peak",
        physics_params={"temp": temp[0]},
        physics_units={"temp": "K"},
        operation="solve",
    )


def _stefan_boltzmann(cleaned: str) -> PhysicsIntent | None:
    """A black body's radiated power."""
    temp = _temperature_value(cleaned, ("temperature", "at", "blackbody"))
    area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN, ("area", "surface"))
    emissivity_match = re.search(
        rf"\bemissivity\s*(?:of|is|=)?\s*({_NUMBER})", cleaned, re.IGNORECASE
    )
    if temp is None or temp[1] != "K" or area is None:
        return None
    return PhysicsIntent(
        kind="modern",
        physics_op="stefan_boltzmann_power",
        physics_params={
            "temp": temp[0],
            "area": area[0],
            "emissivity": float(emissivity_match.group(1)) if emissivity_match else 1.0,
        },
        physics_units={"temp": "K", "area": area[1] or "m^2", "emissivity": ""},
        operation="solve",
    )


def _half_life(cleaned: str) -> PhysicsIntent | None:
    """A sample's remaining mass after a count of half-lives, or a time and its half-life."""
    count = _HALF_LIFE_COUNT_RE.search(cleaned)
    amount = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("sample", "of"))
    if amount is None:
        return None
    params: dict[str, float] = {"m": amount[0]}
    units: dict[str, str] = {"m": amount[1] or "kg"}
    if count is not None:
        params["n_halves"] = float(count.group(1))
        units["n_halves"] = ""
    else:
        half_life_match = re.search(
            rf"\bhalf[- ]life\b\s*(?:of|is|=|:)?\s*({_NUMBER})\s*({_DECAY_TIME_UNITS})\b",
            cleaned,
            re.IGNORECASE,
        )
        elapsed_match = re.search(
            rf"\bafter\s+({_NUMBER})\s*({_DECAY_TIME_UNITS})\b",
            cleaned,
            re.IGNORECASE,
        )
        if half_life_match is None or elapsed_match is None:
            return None
        params.update(
            half_life=float(half_life_match.group(1)),
            elapsed=float(elapsed_match.group(1)),
        )
        units.update(
            half_life=half_life_match.group(2),
            elapsed=elapsed_match.group(2),
        )
    return PhysicsIntent(
        kind="modern",
        physics_op="half_life_remaining",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


def _mass_energy(cleaned: str) -> PhysicsIntent | None:
    """E = mc², only when the question names that energy or writes the equation.

    A leftover modern cue plus a mass is not E = mc².
    """
    if (
        re.search(
            r"\b(?:mass energy|rest energy|energy equivalent)\b"
            r"|\bE\s*=\s*m\s*c(?:\^?2|²)\b",
            cleaned,
            re.IGNORECASE,
        )
        is None
    ):
        return None
    mass = _find_value_with_specific_unit(cleaned, r"kg|grams?|g", ("mass", "of"))
    if mass is None:
        return None
    return PhysicsIntent(
        kind="modern",
        physics_op="mass_energy",
        physics_params={"m": mass[0]},
        physics_units={"m": mass[1] or "kg"},
        operation="solve",
    )
