"""Verified projectile operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "range",
        "projectile",
        "Projectile-motion equation",
        "R",
        assumptions=("constant g, no air resistance, and the same launch and landing height",),
        variants=(FormulaVariant(positive=frozenset({"h0"}), assumptions=()),),
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "max_height",
        "projectile",
        "Projectile-motion equation",
        "H_{max}",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "time_of_flight",
        "projectile",
        "Projectile-motion equation",
        "t_{flight}",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "impact_speed",
        "projectile",
        "Projectile-motion equation",
        "v_{impact}",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "launch_angle",
        "projectile",
        "Projectile-motion equation",
        "\\theta",
        variables=(
            var("d", "d", "meter"),
            var("g", "g", "meter / second ** 2"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
)
