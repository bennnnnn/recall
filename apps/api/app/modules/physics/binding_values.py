"""The values a binding fills without reading them from the question.

A setting an input takes when the question names it without a number (g,
a planet's mass, an electron's charge, water's c), the order a symmetric
pair is filled in, and where a stated value's text ends.
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
from app.modules.physics.catalog.spec import VariableSpec
from app.modules.physics.display import si_symbol
from app.modules.physics.extractors.common import _detect_gravity
from app.modules.physics.givens import Given, unit_dimension, unit_expression


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


def value_end(lower: str, given: Given) -> int:
    """Where a value's text ends: after its unit ("100 kPa"), not its number."""
    unit = given.unit.lower()
    for at in (given.end, given.end + 1):
        if unit and lower.startswith(unit, at):
            return at + len(unit)
    return given.end


def largest_first(params: dict[str, float], units: dict[str, str], names: tuple[str, ...]) -> None:
    """Refill a symmetric pair largest first: the heavier Atwood mass is m₁.

    Values are compared in SI and move with their units: 5 kg outweighs 3000 g.
    """
    present = [name for name in names if name in params]
    pairs = sorted(
        ((params[name], units[name]) for name in present),
        key=lambda pair: _in_si(*pair),
        reverse=True,
    )
    for name, (value, unit) in zip(present, pairs, strict=True):
        params[name] = value
        units[name] = unit


def _in_si(value: float, unit: str) -> float:
    reading = unit_dimension(unit_expression(unit) or "") if unit else None
    return value if reading is None else value * reading[1] + reading[2]
