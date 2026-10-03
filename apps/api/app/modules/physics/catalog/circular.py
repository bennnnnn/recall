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
)
