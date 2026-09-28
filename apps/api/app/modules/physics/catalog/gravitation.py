"""Verified gravitation operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("gravitational_force", "gravitation", "Newton's law of gravitation", "F"),
    formula("orbital_velocity", "gravitation", "Orbital-motion equation", "v"),
    formula("escape_velocity", "gravitation", "Escape-velocity equation", "v_e"),
    formula("surface_gravity", "gravitation", "Surface-gravity equation", "g"),
    formula(
        "gravitational_potential",
        "gravitation",
        "Gravitational potential",
        "V",
        base_latex=r"V = -\frac{GM}{r}",
        assumptions=("zero at infinity",),
    ),
    formula(
        "gravitational_potential_energy",
        "gravitation",
        "Gravitational potential energy",
        "U",
        base_latex=r"U = -\frac{GMm}{r}",
        assumptions=("zero at infinity",),
    ),
    formula(
        "orbital_energy",
        "gravitation",
        "Orbital energy",
        "E",
        base_latex=r"E = -\frac{GMm}{2r}",
        assumptions=("circular orbit",),
    ),
    formula(
        "kepler_period",
        "gravitation",
        "Kepler's third law",
        "T",
        base_latex=r"T = 2\pi\sqrt{\frac{r^3}{GM}}",
        assumptions=("circular orbit around a fixed central mass",),
    ),
)
