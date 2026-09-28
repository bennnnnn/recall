"""Verified circular operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("centripetal_force", "circular", "Circular-motion equation", "F_c"),
    formula("centripetal_acceleration", "circular", "Circular-motion equation", "a_c"),
    formula("orbital_period", "circular", "Orbital-motion equation", "T"),
    formula("angular_velocity", "circular", "Circular-motion equation", "\\omega"),
)
