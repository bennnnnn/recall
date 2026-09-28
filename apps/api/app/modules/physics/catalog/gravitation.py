"""Verified gravitation operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "gravitational_force",
        "gravitation",
        "Newton's law of gravitation",
        "F",
        variables=(
            var("m1", "m_1", "kilogram"),
            var("m2", "m_2", "kilogram"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "orbital_velocity",
        "gravitation",
        "Orbital-motion equation",
        "v",
        variables=(
            var("M", "M", "kilogram"),
            var("altitude", "h", "meter"),
            var("radius_body", "R", "meter"),
        ),
    ),
    formula(
        "escape_velocity",
        "gravitation",
        "Escape-velocity equation",
        "v_e",
        variables=(
            var("M", "M", "kilogram"),
            var("radius_body", "R", "meter"),
        ),
    ),
    formula(
        "surface_gravity",
        "gravitation",
        "Surface-gravity equation",
        "g",
        variables=(
            var("M", "M", "kilogram"),
            var("radius_body", "R", "meter"),
        ),
    ),
    formula(
        "gravitational_potential",
        "gravitation",
        "Gravitational potential",
        "V",
        base_latex=r"V = -\frac{GM}{r}",
        assumptions=("zero at infinity",),
        variables=(
            var("M", "M", "kilogram"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "gravitational_potential_energy",
        "gravitation",
        "Gravitational potential energy",
        "U",
        base_latex=r"U = -\frac{GMm}{r}",
        assumptions=("zero at infinity",),
        variables=(
            var("M", "M", "kilogram"),
            var("m", "m", "kilogram"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "orbital_energy",
        "gravitation",
        "Orbital energy",
        "E",
        base_latex=r"E = -\frac{GMm}{2r}",
        assumptions=("circular orbit",),
        variables=(
            var("M", "M", "kilogram"),
            var("m", "m", "kilogram"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "kepler_period",
        "gravitation",
        "Kepler's third law",
        "T",
        base_latex=r"T = 2\pi\sqrt{\frac{r^3}{GM}}",
        assumptions=("circular orbit around a fixed central mass",),
        variables=(
            var("M", "M", "kilogram"),
            var("r", "r", "meter"),
        ),
    ),
)
