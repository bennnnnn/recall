"""Verified gravitation operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("gravitational_force", "gravitation", "Newton's law of gravitation", "F"),
    formula("orbital_velocity", "gravitation", "Orbital-motion equation", "v"),
    formula("escape_velocity", "gravitation", "Escape-velocity equation", "v_e"),
    formula("surface_gravity", "gravitation", "Surface-gravity equation", "g"),
)
