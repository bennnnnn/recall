"""The values a physics binding fills without reading them from the question.

A setting an input takes when the question names it without a number (g,
a planet's mass, an electron's charge, water's c), in the unit physics writes it.
"""

from __future__ import annotations

from app.modules.physics.bodies import (
    SEA_LEVEL_PRESSURE,
    WATER_DENSITY,
    WATER_SPECIFIC_HEAT,
    named_body,
    named_particle_charge,
    named_particle_mass,
    names_only_water,
)
from app.modules.physics.display import si_symbol
from app.modules.physics.extractors.common import _detect_gravity
from app.services.law_binding.spec import VariableSpec


def fallback_value(variable: VariableSpec, text: str, lower: str) -> float | None:
    """A setting an unstated input takes: g, a named planet's mass, an electron's charge."""
    fallback = variable.fallback
    if fallback == "gravity":
        return _detect_gravity(text)
    if fallback in {"body_mass", "body_radius"}:
        body = named_body(lower)
        return None if body is None else body[0 if fallback == "body_mass" else 1]
    if fallback == "particle_charge":
        return named_particle_charge(lower)
    if fallback == "particle_mass":
        return named_particle_mass(lower)
    if fallback in {"water_specific_heat", "water_density"}:
        if not names_only_water(lower):
            return None
        return WATER_SPECIFIC_HEAT if fallback == "water_specific_heat" else WATER_DENSITY
    if fallback == "sea_level_pressure":
        return SEA_LEVEL_PRESSURE
    return None


def si_unit(variable: VariableSpec) -> str:
    if variable.name.startswith("angle"):
        return "deg"
    return si_symbol(variable.dimension) if variable.dimension else ""
