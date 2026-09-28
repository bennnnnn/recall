"""Verified energy operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "kinetic_energy",
        "energy",
        "Kinetic-energy formula",
        "KE",
        variables=(
            var("m", "m", "kilogram"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "potential_energy",
        "energy",
        "Gravitational potential-energy formula",
        "PE",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h", "h", "meter"),
            var("m", "m", "kilogram"),
        ),
    ),
    formula(
        "work",
        "energy",
        "Work formula",
        "W",
        assumptions=("force parallel to the displacement",),
        variants=(
            FormulaVariant(
                present=frozenset({"angle"}),
                latex=r"W = Fd\cos\theta",
                assumptions=(),
            ),
        ),
        variables=(
            var("F", "F", "newton"),
            var("angle", r"\theta", dimensionless=True),
            var("d", "d", "meter"),
        ),
    ),
    formula(
        "power",
        "energy",
        "Power formula",
        "P",
        assumptions=("force parallel to the velocity",),
        assumptions_require=frozenset({"F", "v"}),
        variants=(
            FormulaVariant(
                present=frozenset({"angle"}),
                latex=r"P = Fv\cos\theta",
                assumptions=(),
            ),
        ),
        variables=(
            var("F", "F", "newton"),
            var("W", "W", "joule"),
            var("angle", r"\theta", dimensionless=True),
            var("t", "t", "second"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "mechanical_efficiency",
        "energy",
        "Mechanical-efficiency formula",
        "\\eta",
        base_latex="\\eta = \\frac{E_{out}}{E_{in}}",
        variables=(
            var("E_in", "E_{in}", "joule"),
            var("E_out", "E_{out}", "joule"),
        ),
    ),
    formula(
        "work_energy",
        "energy",
        "Work-energy theorem",
        "W_{net}",
        base_latex=r"W_{net} = \Delta K",
        assumptions=("net work equals the change in kinetic energy",),
        variables=(
            var("W", "W", "joule"),
            var("m", "m", "kilogram"),
            var("v1", "v_1", "meter / second"),
            var("v2", "v_2", "meter / second"),
        ),
    ),
    formula(
        "mechanical_energy_gravity",
        "energy",
        "Conservation of mechanical energy",
        "E",
        base_latex=r"\frac{1}{2}mv^2 + mgh = \text{constant}",
        assumptions=("no non-conservative work", "g is constant"),
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h1", "h_1", "meter"),
            var("h2", "h_2", "meter"),
            var("v1", "v_1", "meter / second"),
        ),
    ),
    formula(
        "mechanical_energy_spring",
        "energy",
        "Conservation of mechanical energy",
        "E",
        base_latex=r"\frac{1}{2}mv^2 + \frac{1}{2}kx^2 = \text{constant}",
        assumptions=("no non-conservative work",),
        variables=(
            var("k", "k", "newton / meter"),
            var("m", "m", "kilogram"),
            var("v1", "v_1", "meter / second"),
            var("x1", "x_1", "meter"),
            var("x2", "x_2", "meter"),
        ),
    ),
)
