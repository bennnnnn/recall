"""Planets, particles and water: what a question may name instead of giving numbers."""

from __future__ import annotations

from app.services.text_match import word_index

# Mass (kg) and mean radius (m) of each body a school question names.
BODY_PROPERTIES: dict[str, tuple[float, float]] = {
    "earth": (5.9722e24, 6.371e6),
    "moon": (7.342e22, 1.7374e6),
    "mars": (6.4171e23, 3.3895e6),
    "jupiter": (1.8982e27, 6.9911e7),
    "sun": (1.9885e30, 6.957e8),
}


def named_body(lower: str) -> tuple[float, float] | None:
    """(mass, radius) of the first body named in lowercased text, as a whole word."""
    for name, properties in BODY_PROPERTIES.items():
        if word_index(lower, name) != -1:
            return properties
    return None


# The surface gravity (m/s²) a school question takes for a body it names.
# Jupiter and the Sun have no agreed school value (it turns on the radius
# quoted), so a solve that needs g there declines instead of using Earth's.
SCHOOL_GRAVITY: dict[str, float] = {"earth": 9.81, "moon": 1.62, "mars": 3.71}


def names_body_without_school_gravity(lower: str) -> bool:
    """True when lowercased text names a body whose surface g has no school value."""
    return any(
        word_index(lower, name) != -1 for name in BODY_PROPERTIES if name not in SCHOOL_GRAVITY
    )


# Charge magnitude (C) of each particle a question names; e is exact in SI.
ELEMENTARY_CHARGE = 1.602176634e-19
PARTICLE_CHARGES: dict[str, float] = {
    "electron": ELEMENTARY_CHARGE,
    "proton": ELEMENTARY_CHARGE,
    "alpha particle": 2 * ELEMENTARY_CHARGE,
}


def named_particle_charge(lower: str) -> float | None:
    """The charge magnitude of the one particle named in lowercased text."""
    named = [charge for name, charge in PARTICLE_CHARGES.items() if word_index(lower, name) != -1]
    return named[0] if len(named) == 1 else None


# Rest mass (kg) of each particle a question names (CODATA 2018).
ELECTRON_MASS = 9.1093837015e-31
PARTICLE_MASSES: dict[str, float] = {
    "electron": ELECTRON_MASS,
    "proton": 1.67262192369e-27,
    "neutron": 1.67492749804e-27,
    "alpha particle": 6.6446573357e-27,
}


def named_particle_mass(lower: str) -> float | None:
    """The rest mass of the one particle named in lowercased text."""
    named = [mass for name, mass in PARTICLE_MASSES.items() if word_index(lower, name) != -1]
    return named[0] if len(named) == 1 else None


# Water, as a school question means it when it gives no number for it.
WATER_SPECIFIC_HEAT = 4186.0  # J/(kg·K)
WATER_DENSITY = 1000.0  # kg/m³
SEA_LEVEL_PRESSURE = 101325.0  # Pa
# Another substance in the question: water's numbers may not be the ones meant.
_NOT_FRESH_WATER = (
    "sea",
    "salt",
    "ice",
    "steam",
    "oil",
    "mercury",
    "alcohol",
    "ethanol",
    "glycerin",
    "copper",
    "iron",
    "aluminium",
    "aluminum",
    "steel",
    "lead",
    "brass",
    "glass",
    "metal",
)


def names_only_water(lower: str) -> bool:
    """True when the text names water and no other substance its numbers could mean."""
    return word_index(lower, "water") != -1 and all(
        word_index(lower, other) == -1 for other in _NOT_FRESH_WATER
    )
