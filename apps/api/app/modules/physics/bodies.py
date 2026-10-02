"""Planets and stars a question may name instead of giving their numbers."""

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
