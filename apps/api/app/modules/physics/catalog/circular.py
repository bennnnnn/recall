"""Verified circular operations."""

from __future__ import annotations

from app.services.law_binding.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "centripetal_force",
        "circular",
        "Circular-motion equation",
        "F_c",
        variables=(
            var("m", "m", "kilogram"),
            var("omega", r"\omega", "radian / second"),
            var("r", "r", "meter"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "centripetal_acceleration",
        "circular",
        "Circular-motion equation",
        "a_c",
        variables=(
            var("omega", r"\omega", "radian / second"),
            var("r", "r", "meter"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "orbital_period",
        "circular",
        "Orbital-motion equation",
        "T",
        variables=(
            var("omega", r"\omega", "radian / second"),
            var("r", "r", "meter"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "angular_velocity",
        "circular",
        "Circular-motion equation",
        "\\omega",
        variables=(
            var("period", "T", "second"),
            var("r", "r", "meter"),
            var("rpm", "n", "revolution / minute"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "banked_speed",
        "circular",
        "Frictionless banked curve",
        "v",
        base_latex=r"v=\sqrt{rg\tan\theta}",
        assumptions=("No friction", "The bank angle is the design angle"),
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "banked_angle",
        "circular",
        "Frictionless banked curve",
        r"\theta",
        base_latex=r"\theta=\arctan\frac{v^{2}}{rg}",
        assumptions=("No friction",),
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("r", "r", "meter"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "level_curve_speed",
        "circular",
        "Level curve limited by friction",
        "v",
        base_latex=r"v=\sqrt{\mu rg}",
        assumptions=("The road is level", "Friction supplies the centripetal force"),
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("mu", r"\mu", dimensionless=True),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "contact_speed",
        "circular",
        "Speed at which contact force vanishes",
        "v",
        base_latex=r"v=\sqrt{rg}",
        assumptions=("At the top, the normal force or tension is zero",),
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("r", "r", "meter"),
        ),
    ),
)
