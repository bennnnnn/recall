"""Verified friction operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("friction_force", "friction", "Friction law", "f"),
    formula("normal_force", "friction", "Normal-force balance", "N"),
    formula("incline_acceleration", "friction", "Inclined-plane force equation", "a"),
    formula("friction_coefficient", "friction", "Friction law", "\\mu"),
    formula("minimum_force", "friction", "Friction law", "F_{min}"),
)
