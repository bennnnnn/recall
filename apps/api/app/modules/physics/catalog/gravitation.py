"""Verified gravitation operations."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, formula, var

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
            var("M", "M", "kilogram", fallback="body_mass"),
            var("r", "r", "meter"),
        ),
        # Kepler's r is measured from the centre: "400 km above Earth" is a
        # height, and reading it as r would answer an orbit inside the planet.
        binding=Binding(
            asks=("orbital period", "period"),
            result=("second",),
            inputs=(frozenset({"M", "r"}),),
            cues=("radius", "from the centre", "from the center"),
            excludes=("above", "altitude", "height"),
            nonnegative=True,
        ),
    ),
    # "400 km above Earth": the orbit's radius is the planet's plus that height.
    formula(
        "kepler_period_altitude",
        "gravitation",
        "Kepler's third law",
        "T",
        base_latex=r"T = 2\pi\sqrt{\frac{(R + h)^3}{GM}}",
        assumptions=("circular orbit around a fixed central mass",),
        expression="2*pi*sqrt((radius_body + altitude)**3/(G_grav*M))",
        variables=(
            var("M", "M", "kilogram", fallback="body_mass"),
            var(
                "altitude",
                "h",
                "meter",
                words=("above", "altitude", "height"),
                needs_words=True,
            ),
            var("radius_body", "R", "meter", fallback="body_radius"),
        ),
        binding=Binding(
            asks=("orbital period", "period"),
            result=("second",),
            inputs=(frozenset({"M", "altitude", "radius_body"}),),
            cues=("orbit",),
            nonnegative=True,
        ),
    ),
)
