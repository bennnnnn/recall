"""Verified materials operations."""

from __future__ import annotations

from app.services.law_binding.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "stress",
        "materials",
        "Stress formula",
        "\\sigma",
        variables=(
            var("F", "F", "newton"),
            var("area", "A", "meter ** 2"),
        ),
    ),
    formula(
        "strain",
        "materials",
        "Strain formula",
        "\\varepsilon",
        variables=(
            var("L0", "L_0", "meter"),
            var("dL", r"\Delta L", "meter"),
        ),
    ),
    formula(
        "youngs_modulus",
        "materials",
        "Young's modulus formula",
        "E",
        variables=(
            var("sigma", r"\sigma", "pascal"),
            var("strain", r"\epsilon", dimensionless=True),
        ),
    ),
)
