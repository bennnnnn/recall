"""Verified friction operations."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

_STATE = (
    var("static_equilibrium", "static", dimensionless=True, visible=False),
    var("motion_sign", "direction", dimensionless=True, visible=False),
    var("released_from_rest", "initial", dimensionless=True, visible=False),
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
            *_STATE,
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
            excludes=("static", "rests", "resting", "at rest"),
            # Friction stronger than the pull leaves the body at rest, not
            # accelerating backwards.
            nonnegative=True,
        ),
    ),
    # Pushed or pulled up an incline by a force along it. The incline law alone
    # left the push out: 30 N up a frictionless 25° slope gave 4.15 m/s² down
    # the slope instead of 5.85 m/s² up it.
    formula(
        "incline_push_acceleration",
        "friction",
        "Newton's second law along an incline",
        "a",
        base_latex=r"F - mg\sin\theta - \mu mg\cos\theta = ma",
        assumptions=(
            "the force acts along the slope, up it",
            "kinetic friction opposes the motion up the slope",
        ),
        expression="(F - m*g*(sin(angle) + mu*cos(angle)))/m",
        variables=(
            var("F", "F", "newton"),
            var("g", "g", "meter / second ** 2", fallback="gravity"),
            var("m", "m", "kilogram"),
            var("angle", r"\theta", dimensionless=True),
            var(
                "mu",
                r"\mu",
                dimensionless=True,
                implied=(("frictionless", 0.0), ("smooth", 0.0)),
            ),
        ),
        binding=Binding(
            asks=("acceleration",),
            result=("meter / second ** 2",),
            inputs=(frozenset({"F", "g", "m", "angle", "mu"}),),
            cues=(
                "parallel to the slope",
                "parallel to the incline",
                "parallel to the ramp",
                "along the slope",
                "along the incline",
                "along the ramp",
            ),
            excludes=("horizontal force", "horizontally", "down the", "static", "rests", "at rest"),
            # A push too weak to move it up the slope: it does not accelerate up.
            nonnegative=True,
        ),
    ),
    # Friction alone slows a sliding body at mu*g.
    formula(
        "friction_deceleration",
        "friction",
        "Friction law",
        "a",
        base_latex=r"a = \mu g",
        assumptions=("friction is the only horizontal force",),
        expression="mu*g",
        variables=(
            var("mu", r"\mu", dimensionless=True),
            var("g", "g", "meter / second ** 2", fallback="gravity"),
        ),
        binding=Binding(
            asks=("maximum deceleration", "deceleration", "maximum acceleration"),
            result=("meter / second ** 2",),
            inputs=(frozenset({"mu", "g"}),),
            cues=("friction", "coefficient"),
            nonnegative=True,
        ),
    ),
    formula(
        "friction_sliding_distance",
        "friction",
        "Friction law",
        "d",
        base_latex=r"d = \frac{v^2}{2 \mu g}",
        assumptions=("friction is the only horizontal force",),
        expression="v**2/(2*mu*g)",
        variables=(
            var("v", "v", "meter / second"),
            var("mu", r"\mu", dimensionless=True),
            var("g", "g", "meter / second ** 2", fallback="gravity"),
        ),
        binding=Binding(
            asks=("how far", "distance", "stopping distance"),
            result=("meter",),
            inputs=(frozenset({"v", "mu", "g"}),),
            cues=("friction", "coefficient"),
            nonnegative=True,
        ),
    ),
)
