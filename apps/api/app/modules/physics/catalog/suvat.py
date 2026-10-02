"""Verified suvat operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "suvat_velocity",
        "suvat",
        "SUVAT constant-acceleration equation",
        "v",
        base_latex="v = u + at",
        variants=(
            FormulaVariant(
                latex=r"v = \sqrt{u^2 + 2as}",
                present=frozenset({"d"}),
                absent=frozenset({"t"}),
            ),
            FormulaVariant(
                latex=r"v = \frac{2s}{t} - u",
                present=frozenset({"d", "t"}),
                absent=frozenset({"a"}),
            ),
        ),
        variables=(
            var("a", "a", "meter / second ** 2"),
            var("d", "s", "meter"),
            var("t", "t", "second"),
            var("u", "u", "meter / second"),
        ),
    ),
    formula(
        "suvat_distance",
        "suvat",
        "SUVAT constant-acceleration equation",
        "s",
        base_latex=r"s = ut + \tfrac{1}{2}at^2",
        variants=(
            FormulaVariant(
                latex=r"s = \frac{v^2 - u^2}{2a}",
                present=frozenset({"v"}),
                absent=frozenset({"t"}),
            ),
            FormulaVariant(
                latex=r"s = \tfrac{1}{2}(u + v)t",
                present=frozenset({"v", "t"}),
                absent=frozenset({"a"}),
            ),
        ),
        variables=(
            var("a", "a", "meter / second ** 2"),
            var("t", "t", "second"),
            var("u", "u", "meter / second"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "suvat_time",
        "suvat",
        "SUVAT constant-acceleration equation",
        "t",
        base_latex="v = u + at",
        variants=(
            FormulaVariant(
                latex=r"\tfrac{1}{2}at^2 + ut - s = 0",
                present=frozenset({"d"}),
                absent=frozenset({"v"}),
            ),
            FormulaVariant(
                latex=r"t = \frac{2s}{u + v}",
                present=frozenset({"d", "v"}),
                absent=frozenset({"a"}),
            ),
        ),
        variables=(
            var("a", "a", "meter / second ** 2"),
            var("d", "s", "meter"),
            var("u", "u", "meter / second"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "suvat_acceleration",
        "suvat",
        "SUVAT constant-acceleration equation",
        "a",
        base_latex="v = u + at",
        variants=(
            FormulaVariant(
                latex=r"a = \frac{v^2 - u^2}{2s}",
                present=frozenset({"d"}),
                absent=frozenset({"t"}),
            ),
            FormulaVariant(
                latex=r"a = \frac{2(s - ut)}{t^2}",
                present=frozenset({"d", "t"}),
                absent=frozenset({"v"}),
            ),
        ),
        variables=(
            var("d", "s", "meter"),
            var("t", "t", "second"),
            var("u", "u", "meter / second"),
            var("v", "v", "meter / second"),
        ),
    ),
)
