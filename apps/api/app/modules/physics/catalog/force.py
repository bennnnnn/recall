"""Verified force operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("net_force", "force", "Newton's second law", "F", base_latex="F = ma"),
    formula("tension", "force", "Newton's second law", "T"),
    formula("atwood", "force", "Newton's second law", "a,\\ T"),
    formula("resultant_force", "force", "Vector addition and components", "R"),
    formula("resolve_force", "force", "Vector addition and components", "F_x,\\ F_y"),
)
