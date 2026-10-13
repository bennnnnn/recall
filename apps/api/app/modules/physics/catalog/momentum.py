"""Verified momentum operations."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "momentum_change_rebound",
        "momentum",
        "Change in momentum",
        r"\Delta p",
        # Into the wall and back out: the velocity reverses, so the sizes add.
        base_latex=r"\Delta p = m(v_1 + v_2)",
        assumptions=("the object comes straight back along its path",),
        expression="m*(v_in + v_out)",
        variables=(
            var("m", "m", "kilogram"),
            var("v_in", "v_1", "meter / second"),
            var("v_out", "v_2", "meter / second"),
        ),
        binding=Binding(
            asks=("change in momentum", "change of momentum", "impulse"),
            result=("kilogram * meter / second",),
            inputs=(frozenset({"m", "v_in", "v_out"}),),
            cues=("rebound", "rebounds", "bounces back", "bounces off", "comes back"),
            interchangeable=("v_in", "v_out"),
            nonnegative=True,
        ),
    ),
    formula(
        "momentum",
        "momentum",
        "Linear-momentum formula",
        "p",
        variables=(
            var("m", "m", "kilogram"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "impulse",
        "momentum",
        "Impulse-momentum theorem",
        "J",
        variables=(
            var("F", "F", "newton"),
            var("dt", r"\Delta t", "second"),
            var("m", "m", "kilogram"),
            var("v1", "v_1", "meter / second"),
            var("v2", "v_2", "meter / second"),
        ),
    ),
    formula(
        "final_velocity",
        "momentum",
        "Conservation of linear momentum",
        "v_f",
        variants=(
            FormulaVariant(
                equals=(("elastic", 1.0),),
                result_symbol=r"v_1',\ v_2'",
                lines=(
                    r"v_1' = \frac{(m_1-m_2)v_1 + 2m_2v_2}{m_1+m_2}",
                    r"v_2' = \frac{(m_2-m_1)v_2 + 2m_1v_1}{m_1+m_2}",
                ),
            ),
            FormulaVariant(
                lines=(
                    r"m_1v_1 + m_2v_2 = (m_1+m_2)v_f",
                    r"v_f = \frac{m_1v_1 + m_2v_2}{m_1+m_2}",
                ),
            ),
        ),
        variables=(
            var("elastic", "elastic", dimensionless=True, visible=False),
            var("m1", "m_1", "kilogram"),
            var("m2", "m_2", "kilogram"),
            var("v1", "v_1", "meter / second"),
            var("v2", "v_2", "meter / second"),
        ),
    ),
    formula(
        "center_of_mass",
        "momentum",
        "Center-of-mass equation",
        "x_{cm}",
        base_latex="x_{cm} = \\frac{m_1x_1 + m_2x_2}{m_1 + m_2}",
        variables=(
            var("m1", "m_1", "kilogram"),
            var("m2", "m_2", "kilogram"),
            var("x1", "x_1", "meter"),
            var("x2", "x_2", "meter"),
        ),
    ),
    formula(
        "center_of_mass_three",
        "momentum",
        "Center of mass of three masses",
        "x_{cm}",
        base_latex=r"x_{cm} = \frac{m_1x_1 + m_2x_2 + m_3x_3}{m_1 + m_2 + m_3}",
        expression="(m1*x1+m2*x2+m3*x3)/(m1+m2+m3)",
        variables=(
            var("m1", "m_1", "kilogram"),
            var("m2", "m_2", "kilogram"),
            var("m3", "m_3", "kilogram"),
            var("x1", "x_1", "meter"),
            var("x2", "x_2", "meter"),
            var("x3", "x_3", "meter"),
        ),
        binding=Binding(
            asks=("center of mass", "centre of mass"),
            result=("meter",),
            inputs=(frozenset({"m1", "m2", "m3", "x1", "x2", "x3"}),),
            cues=("center of mass", "centre of mass"),
            nonnegative=False,
        ),
    ),
    formula(
        "rocket_delta_v",
        "kinematics",
        "Rocket equation",
        r"\Delta v",
        base_latex=r"\Delta v = v_e\ln\frac{m_0}{m}",
        assumptions=("the exhaust speed is constant", "no external force"),
        expression="v_exhaust*log(m_initial/m_final)",
        variables=(
            var(
                "v_exhaust",
                "v_e",
                "meter / second",
                words=("exhaust", "exhausts", "ejected", "ejects"),
                needs_words=True,
            ),
            var("m_initial", "m_0", "kilogram", words=("from", "initial"), needs_words=True),
            var("m_final", "m", "kilogram", words=("to", "final"), needs_words=True),
        ),
        binding=Binding(
            asks=("change in speed", "speed change", "delta v"),
            result=("meter / second",),
            inputs=(frozenset({"m_final", "m_initial", "v_exhaust"}),),
            cues=("rocket",),
            nonnegative=True,
        ),
    ),
    formula(
        "reduced_mass",
        "force",
        "Reduced mass",
        r"\mu",
        base_latex=r"\mu = \frac{m_1 m_2}{m_1 + m_2}",
        expression="m1*m2/(m1+m2)",
        variables=(
            var("m1", "m_1", "kilogram"),
            var("m2", "m_2", "kilogram"),
        ),
        binding=Binding(
            asks=("reduced mass",),
            result=("kilogram",),
            inputs=(frozenset({"m1", "m2"}),),
            cues=("reduced mass",),
            interchangeable=("m1", "m2"),
            nonnegative=True,
        ),
    ),
    formula(
        "restitution",
        "momentum",
        "Coefficient of restitution",
        "e",
        base_latex=r"e = \frac{v_{\mathrm{sep}}}{v_{\mathrm{app}}}",
        assumptions=("one dimension",),
        expression="v_sep/v_app",
        variables=(
            var(
                "v_app",
                r"v_{\mathrm{app}}",
                "meter / second",
                words=("approach", "before"),
                needs_words=True,
            ),
            var(
                "v_sep",
                r"v_{\mathrm{sep}}",
                "meter / second",
                words=("separate", "separation", "after", "rebound"),
                needs_words=True,
            ),
        ),
        binding=Binding(
            asks=("coefficient of restitution", "restitution"),
            result=("dimensionless",),
            inputs=(frozenset({"v_app", "v_sep"}),),
            cues=("restitution",),
            nonnegative=True,
        ),
    ),
)
