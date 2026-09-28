"""Verified materials operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "stress",
        "materials",
        "Stress formula",
        "\\sigma",
        variables=(
            var("F", "F", "newton"),
            var("area", "area", "meter ** 2"),
        ),
    ),
    formula(
        "strain",
        "materials",
        "Strain formula",
        "\\varepsilon",
        variables=(
            var("L0", "L_0", "meter"),
            var("dL", "dL", "meter"),
        ),
    ),
    formula(
        "youngs_modulus",
        "materials",
        "Young's modulus formula",
        "E",
        variables=(
            var("sigma", "sigma", "pascal"),
            var("strain", "strain", dimensionless=True),
        ),
    ),
)
