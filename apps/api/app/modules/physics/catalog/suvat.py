"""Verified suvat operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "suvat_velocity",
        "suvat",
        "SUVAT constant-acceleration equation",
        "v",
        base_latex="v = u + at",
    ),
    formula(
        "suvat_distance",
        "suvat",
        "SUVAT constant-acceleration equation",
        "s",
        base_latex="s = ut + \\frac{1}{2}at^2",
    ),
    formula(
        "suvat_time", "suvat", "SUVAT constant-acceleration equation", "t", base_latex="v = u + at"
    ),
    formula(
        "suvat_acceleration",
        "suvat",
        "SUVAT constant-acceleration equation",
        "a",
        base_latex="v = u + at",
    ),
)
