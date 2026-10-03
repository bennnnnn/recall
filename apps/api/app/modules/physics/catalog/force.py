"""Verified force operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import Binding, FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "net_force",
        "force",
        "Newton's second law",
        "F",
        base_latex="F = ma",
        solve_for=(("F", "F"), ("m", "m"), ("a", "a")),
        variables=(
            var("F", "F", "newton"),
            var("a", "a", "meter / second ** 2"),
            var("m", "m", "kilogram"),
        ),
    ),
    formula(
        "tension",
        "force",
        "Newton's second law",
        "T",
        variables=(
            var("a", "a", "meter / second ** 2"),
            var("g", "g", "meter / second ** 2", visible=False),
            var("m", "m", "kilogram"),
        ),
    ),
    formula(
        "atwood",
        "force",
        "Newton's second law",
        "a,\\ T",
        variables=(
            var("g", "g", "meter / second ** 2", visible=False),
            var("m1", "m_1", "kilogram"),
            var("m2", "m_2", "kilogram"),
        ),
        # Two masses over a pulley; the heavier is m₁, so the acceleration is its fall.
        binding=Binding(
            asks=("acceleration", "tension"),
            result=("meter / second ** 2", "newton"),
            inputs=(frozenset({"m1", "m2"}),),
            cues=("pulley", "atwood"),
            descending=("m1", "m2"),
        ),
    ),
    formula(
        "resultant_force",
        "force",
        "Vector addition and components",
        "R",
        variables=(
            var("F1", "F_1", "newton"),
            var("F2", "F_2", "newton"),
            var("angle", r"\theta", dimensionless=True),
        ),
    ),
    formula(
        "resolve_force",
        "force",
        "Vector addition and components",
        "F_x,\\ F_y",
        variables=(
            var("F", "F", "newton"),
            var("angle", r"\theta", dimensionless=True),
        ),
    ),
    formula(
        "weight",
        "force",
        "Weight equation",
        "W",
        base_latex="W = mg",
        expression="m*g",
        variables=(
            var("g", "g", "meter / second ** 2", fallback="gravity"),
            var("m", "m", "kilogram"),
        ),
        binding=Binding(
            asks=("weight",),
            result=("newton",),
            inputs=(frozenset({"g", "m"}),),
            nonnegative=True,
        ),
    ),
    formula(
        "mass_from_weight",
        "force",
        "Weight equation",
        "m",
        base_latex="W = mg",
        expression="weight/g",
        variables=(
            var("g", "g", "meter / second ** 2", fallback="gravity"),
            var("weight", "W", "newton"),
        ),
        binding=Binding(
            asks=("mass",),
            result=("kilogram",),
            inputs=(frozenset({"g", "weight"}),),
            cues=("weigh",),
            nonnegative=True,
        ),
    ),
)
