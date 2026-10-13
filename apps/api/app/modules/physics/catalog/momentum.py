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
)
