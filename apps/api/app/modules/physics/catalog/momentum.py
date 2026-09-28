"""Verified momentum operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("momentum", "momentum", "Linear-momentum formula", "p"),
    formula("impulse", "momentum", "Impulse-momentum theorem", "J"),
    formula("final_velocity", "momentum", "Conservation of linear momentum", "v_f"),
    formula(
        "center_of_mass",
        "momentum",
        "Center-of-mass equation",
        "x_{cm}",
        base_latex="x_{cm} = \\frac{m_1x_1 + m_2x_2}{m_1 + m_2}",
    ),
)
