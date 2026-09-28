"""Verified magnetism operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("magnetic_force_wire", "magnetism", "Magnetic force on a wire", "F"),
    formula(
        "magnetic_force_charge",
        "magnetism",
        "Lorentz magnetic-force law",
        "F",
        assumptions=("velocity is perpendicular to the field",),
    ),
    formula(
        "electric_force",
        "magnetism",
        "Coulomb's law",
        "F_e",
        base_latex="F_e = k_e \\frac{\\lvert q_1q_2\\rvert}{r^2}",
    ),
    formula("magnetic_flux", "magnetism", "Magnetic-flux formula", "\\Phi"),
    formula(
        "electric_field",
        "magnetism",
        "Electric field of a point charge",
        "E",
        base_latex="E = k_e\\frac{\\lvert Q\\rvert}{r^2}",
    ),
    formula(
        "electric_potential",
        "magnetism",
        "Electric potential of a point charge",
        "V",
        base_latex="V = k_e\\frac{Q}{r}",
    ),
    formula(
        "electric_potential_energy",
        "magnetism",
        "Electric potential-energy equation",
        "U",
        base_latex="U = k_e\\frac{q_1q_2}{r}",
    ),
    formula(
        "charged_particle_radius",
        "magnetism",
        "Charged-particle magnetic radius",
        "r",
        base_latex="r = \\frac{mv}{\\lvert q\\rvert B}",
    ),
    formula(
        "motional_emf",
        "magnetism",
        "Motional-emf equation",
        "\\mathcal{E}",
        base_latex="\\mathcal{E} = BLv",
    ),
    formula(
        "magnetic_field_wire",
        "magnetism",
        "Magnetic field of a straight wire",
        "B",
        base_latex="B = \\frac{\\mu_0I}{2\\pi r}",
    ),
)
