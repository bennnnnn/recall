"""Verified kinematics operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "position",
        "kinematics",
        "Constant-acceleration equation",
        "h",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("t", "t", "second"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "velocity",
        "kinematics",
        "Constant-acceleration equation",
        "v",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("t", "t", "second"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "time_to_ground",
        "kinematics",
        "Constant-acceleration equation",
        "t",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "speed",
        "kinematics",
        "Constant-acceleration equation",
        "v",
        variants=(FormulaVariant(absent=frozenset({"t"}), result_symbol="v_{impact}"),),
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("t", "t", "second"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "acceleration",
        "kinematics",
        "Constant-acceleration equation",
        "a",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "vertical_max_height",
        "kinematics",
        "Constant-acceleration equation",
        "h_{\\max}",
        base_latex=r"h_{\max} = h_0 + \frac{v_0^2}{2g}",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "average_speed",
        "kinematics",
        "Distance-speed-time equation",
        "v",
        base_latex="v = \\frac{d}{t}",
        variables=(
            var("d", "d", "meter"),
            var("t", "t", "second"),
        ),
    ),
    formula(
        "rate_speed",
        "kinematics",
        "Distance-speed-time equation",
        "v",
        base_latex="v = \\frac{d}{t}",
        variables=(
            var("d", "d", "meter"),
            var("t", "t", "second"),
        ),
    ),
    formula(
        "rate_distance",
        "kinematics",
        "Distance-speed-time equation",
        "d",
        base_latex="v = \\frac{d}{t}",
        variables=(
            var("t", "t", "second"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "rate_time",
        "kinematics",
        "Distance-speed-time equation",
        "t",
        base_latex="v = \\frac{d}{t}",
        variables=(
            var("d", "d", "meter"),
            var("v", "v", "meter / second"),
        ),
    ),
)
