"""Verified friction operations."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, formula, var

_STATE = (
    var("static_equilibrium", "static", dimensionless=True, visible=False),
    var("motion_sign", "direction", dimensionless=True, visible=False),
)

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "friction_force",
        "friction",
        "Friction law",
        "f",
        variables=(
            *_STATE,
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
    ),
    formula(
        "normal_force",
        "friction",
        "Normal-force balance",
        "N",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
    ),
    formula(
        "incline_acceleration",
        "friction",
        "Inclined-plane force equation",
        "a",
        variables=(
            *_STATE,
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
    ),
    formula(
        "friction_coefficient",
        "friction",
        "Friction law",
        "\\mu",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
        ),
    ),
    formula(
        "minimum_force",
        "friction",
        "Friction law",
        "F_{min}",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
    ),
    # Pulled along a level floor against kinetic friction.
    formula(
        "applied_friction_acceleration",
        "friction",
        "Newton's second law with friction",
        "a",
        base_latex=r"F - \mu mg = ma",
        assumptions=("a horizontal pull on a level surface", "kinetic friction"),
        expression="(F - mu*m*g)/m",
        variables=(
            var("F", "F", "newton"),
            var("g", "g", "meter / second ** 2", fallback="gravity"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
        binding=Binding(
            asks=("acceleration",),
            result=("meter / second ** 2",),
            inputs=(frozenset({"F", "g", "m", "mu"}),),
            cues=("friction",),
            excludes=("static", "rests", "resting", "at rest"),
            # Friction stronger than the pull leaves the body at rest, not
            # accelerating backwards.
            nonnegative=True,
        ),
    ),
)
