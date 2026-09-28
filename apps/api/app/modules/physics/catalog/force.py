"""Verified force operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "net_force",
        "force",
        "Newton's second law",
        "F",
        base_latex="F = ma",
        variables=(
            var("F", "F", "newton"),
            var("a", "a", "meter / second ** 2"),
            var("m", "m", "kilogram"),
        ),
    ),
    formula(
        "tension",
        "force",
        "Newton's second law",
        "T",
        variables=(
            var("a", "a", "meter / second ** 2"),
            var("m", "m", "kilogram"),
        ),
    ),
    formula(
        "atwood",
        "force",
        "Newton's second law",
        "a,\\ T",
        variables=(
            var("m1", "m_1", "kilogram"),
            var("m2", "m_2", "kilogram"),
        ),
    ),
    formula(
        "resultant_force",
        "force",
        "Vector addition and components",
        "R",
        variables=(
            var("F1", "F_1", "newton"),
            var("F2", "F_2", "newton"),
            var("angle", r"\theta", dimensionless=True),
        ),
    ),
    formula(
        "resolve_force",
        "force",
        "Vector addition and components",
        "F_x,\\ F_y",
        variables=(
            var("F", "F", "newton"),
            var("angle", r"\theta", dimensionless=True),
        ),
    ),
)
