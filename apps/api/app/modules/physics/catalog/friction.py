"""Verified friction operations."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "friction_force",
        "friction",
        "Friction law",
        "f",
        variables=(
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
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu", r"\mu", dimensionless=True),
        ),
    ),
    formula(
        "incline_sliding",
        "friction",
        "Static-friction threshold",
        r"\text{Will it start sliding?}",
        base_latex=(
            r"F_{g,\parallel} > f_{s,\max}"
            r" \quad\Longleftrightarrow\quad "
            r"mg\sin\theta > \mu_s mg\cos\theta"
        ),
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("mu_s", r"\mu_s", dimensionless=True),
        ),
        variants=(
            FormulaVariant(
                present=frozenset({"mu_s"}),
                lines=(
                    r"F_{g,\parallel}=mg\sin\theta",
                    r"f_{s,\max}=\mu_sN=\mu_smg\cos\theta",
                    r"F_{g,\parallel}>f_{s,\max}"
                    r" \quad\Longleftrightarrow\quad "
                    r"mg\sin\theta>\mu_smg\cos\theta",
                ),
            ),
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
            # Friction stronger than the pull leaves the body at rest, not
            # accelerating backwards.
            nonnegative=True,
        ),
    ),
)
