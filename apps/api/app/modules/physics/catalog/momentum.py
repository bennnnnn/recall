"""Verified momentum operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
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
