"""Verified friction operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "friction_force",
        "friction",
        "Friction law",
        "f",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
    ),
    formula(
        "normal_force",
        "friction",
        "Normal-force balance",
        "N",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
    ),
    formula(
        "incline_acceleration",
        "friction",
        "Inclined-plane force equation",
        "a",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
    ),
    formula(
        "friction_coefficient",
        "friction",
        "Friction law",
        "\\mu",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
        ),
    ),
    formula(
        "minimum_force",
        "friction",
        "Friction law",
        "F_{min}",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
    ),
)
