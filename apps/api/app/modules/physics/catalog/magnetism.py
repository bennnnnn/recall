"""Verified magnetism operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "magnetic_force_wire",
        "magnetism",
        "Magnetic force on a wire",
        "F",
        base_latex="F = BIL",
        assumptions=("current is perpendicular to the field",),
        variants=(
            FormulaVariant(
                present=frozenset({"angle"}),
                latex=r"F = BIL\sin\theta",
                assumptions=(),
            ),
        ),
        variables=(
            var("I", "I", "ampere"),
            var("angle", r"\theta", dimensionless=True),
            var("b_field", "B", "tesla"),
            var("wire_L", "L", "meter"),
        ),
    ),
    formula(
        "magnetic_force_charge",
        "magnetism",
        "Lorentz magnetic-force law",
        "F",
        base_latex="F = qvB",
        assumptions=("velocity is perpendicular to the field",),
        variants=(
            FormulaVariant(
                present=frozenset({"angle"}),
                latex=r"F = qvB\sin\theta",
                assumptions=(),
            ),
        ),
        variables=(
            var("Q", "Q", "coulomb"),
            var("angle", r"\theta", dimensionless=True),
            var("b_field", "B", "tesla"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "electric_force",
        "magnetism",
        "Coulomb's law",
        "F_e",
        base_latex="F_e = k_e \\frac{\\lvert q_1q_2\\rvert}{r^2}",
        variables=(
            var("q1", "q_1", "coulomb"),
            var("q2", "q_2", "coulomb"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "magnetic_flux",
        "magnetism",
        "Magnetic-flux formula",
        "\\Phi",
        base_latex=r"\Phi = BA",
        assumptions=("area is perpendicular to the field",),
        variants=(
            FormulaVariant(
                present=frozenset({"angle"}),
                latex=r"\Phi = BA\cos\theta",
                assumptions=(),
            ),
        ),
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("area", "area", "meter ** 2"),
            var("b_field", "B", "tesla"),
        ),
    ),
    formula(
        "gauss_outside",
        "magnetism",
        "Gauss's law outside a sphere",
        "E",
        base_latex=r"E = k\frac{|Q|}{r^2}",
        assumptions=("spherical symmetry, outside the charge",),
        variables=(
            var("Q", "Q", "coulomb"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "gauss_inside_shell",
        "magnetism",
        "Gauss's law inside a shell",
        "E",
        base_latex="E = 0",
        assumptions=("thin spherical shell",),
        variables=(
            var("Q", "Q", "coulomb"),
            var("r", "r", "meter"),
            var("radius_body", "R", "meter"),
        ),
    ),
    formula(
        "gauss_inside_sphere",
        "magnetism",
        "Gauss's law inside a uniform sphere",
        "E",
        base_latex=r"E = k\frac{|Q|r}{R^3}",
        assumptions=("charge is spread uniformly through the sphere",),
        variables=(
            var("Q", "Q", "coulomb"),
            var("r", "r", "meter"),
            var("radius_body", "R", "meter"),
        ),
    ),
    formula(
        "gauss_line",
        "magnetism",
        "Gauss's law for a line",
        "E",
        base_latex=r"E = \frac{2k|\lambda|}{r}",
        assumptions=("infinite straight line",),
        variables=(
            var("lambda_line", r"\lambda", "coulomb / meter"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "gauss_plane",
        "magnetism",
        "Gauss's law for a sheet",
        "E",
        base_latex=r"E = \frac{|\sigma|}{2\epsilon_0}",
        assumptions=("infinite nonconducting sheet",),
        variables=(var("sigma_charge", r"\sigma", "coulomb / meter ** 2"),),
    ),
    formula(
        "faraday_emf",
        "magnetism",
        "Faraday's law",
        r"|\mathcal{E}|",
        base_latex=r"|\mathcal{E}| = N\frac{|\Delta\Phi|}{\Delta t}",
        assumptions=("magnitude; the minus sign is direction",),
        variables=(
            var("delta_flux", "delta_flux", "weber"),
            var("dt", "dt", "second"),
            var("turns", "turns", dimensionless=True),
        ),
    ),
    formula(
        "electric_field",
        "magnetism",
        "Electric field of a point charge",
        "E",
        base_latex="E = k_e\\frac{\\lvert Q\\rvert}{r^2}",
        variables=(
            var("Q", "Q", "coulomb"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "electric_potential",
        "magnetism",
        "Electric potential of a point charge",
        "V",
        base_latex="V = k_e\\frac{Q}{r}",
        variables=(
            var("Q", "Q", "coulomb"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "electric_potential_energy",
        "magnetism",
        "Electric potential-energy equation",
        "U",
        base_latex="U = k_e\\frac{q_1q_2}{r}",
        variables=(
            var("q1", "q_1", "coulomb"),
            var("q2", "q_2", "coulomb"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "charged_particle_radius",
        "magnetism",
        "Charged-particle magnetic radius",
        "r",
        base_latex="r = \\frac{mv}{\\lvert q\\rvert B}",
        variables=(
            var("Q", "Q", "coulomb"),
            var("b_field", "B", "tesla"),
            var("m", "m", "kilogram"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "motional_emf",
        "magnetism",
        "Motional-emf equation",
        "\\mathcal{E}",
        base_latex="\\mathcal{E} = BLv",
        variables=(
            var("b_field", "B", "tesla"),
            var("v", "v", "meter / second"),
            var("wire_L", "L", "meter"),
        ),
    ),
    formula(
        "magnetic_field_wire",
        "magnetism",
        "Magnetic field of a straight wire",
        "B",
        base_latex="B = \\frac{\\mu_0I}{2\\pi r}",
        variables=(
            var("I", "I", "ampere"),
            var("r", "r", "meter"),
        ),
    ),
)
