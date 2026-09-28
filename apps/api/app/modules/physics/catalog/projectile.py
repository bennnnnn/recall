"""Verified projectile operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "range",
        "projectile",
        "Projectile-motion equation",
        "R",
        assumptions=("constant g, no air resistance, and the same launch and landing height",),
    ),
    formula("max_height", "projectile", "Projectile-motion equation", "H_{max}"),
    formula("time_of_flight", "projectile", "Projectile-motion equation", "t_{flight}"),
    formula("impact_speed", "projectile", "Projectile-motion equation", "v_{impact}"),
    formula("launch_angle", "projectile", "Projectile-motion equation", "\\theta"),
)
