"""Verified materials operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("stress", "materials", "Stress formula", "\\sigma"),
    formula("strain", "materials", "Strain formula", "\\varepsilon"),
    formula("youngs_modulus", "materials", "Young's modulus formula", "E"),
)
