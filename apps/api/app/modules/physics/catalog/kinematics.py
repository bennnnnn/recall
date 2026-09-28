"""Verified kinematics operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("position", "kinematics", "Constant-acceleration equation", "h"),
    formula("velocity", "kinematics", "Constant-acceleration equation", "v"),
    formula("time_to_ground", "kinematics", "Constant-acceleration equation", "t"),
    formula("speed", "kinematics", "Constant-acceleration equation", "v"),
    formula("acceleration", "kinematics", "Constant-acceleration equation", "a"),
    formula(
        "average_speed",
        "kinematics",
        "Distance-speed-time equation",
        "v",
        base_latex="v = \\frac{d}{t}",
    ),
    formula(
        "rate_speed",
        "kinematics",
        "Distance-speed-time equation",
        "v",
        base_latex="v = \\frac{d}{t}",
    ),
    formula(
        "rate_distance",
        "kinematics",
        "Distance-speed-time equation",
        "d",
        base_latex="v = \\frac{d}{t}",
    ),
    formula(
        "rate_time",
        "kinematics",
        "Distance-speed-time equation",
        "t",
        base_latex="v = \\frac{d}{t}",
    ),
)
