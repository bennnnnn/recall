"""Verified thermal operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("heat_energy", "thermal", "Specific-heat equation", "Q"),
    formula("ideal_gas_pressure", "thermal", "Ideal-gas law", "P", base_latex="PV = nRT"),
    formula("thermal_efficiency", "thermal", "Thermal-efficiency formula", "\\eta"),
    formula(
        "linear_expansion",
        "thermal",
        "Linear thermal-expansion law",
        "\\Delta L",
        base_latex="\\Delta L = \\alpha L_0\\Delta T",
    ),
    formula("latent_heat", "thermal", "Latent-heat equation", "Q", base_latex="Q = mL"),
    formula(
        "first_law_internal_energy",
        "thermal",
        "First law of thermodynamics",
        "\\Delta U",
        base_latex="\\Delta U = Q - W",
    ),
    formula(
        "carnot_efficiency",
        "thermal",
        "Carnot-efficiency equation",
        "\\eta_C",
        base_latex="\\eta_C = 1 - \\frac{T_C}{T_H}",
    ),
    formula(
        "entropy_change",
        "thermal",
        "Entropy-change equation",
        "\\Delta S",
        base_latex="\\Delta S = \\frac{Q_{rev}}{T}",
    ),
    formula(
        "heat_conduction_rate",
        "thermal",
        "Fourier heat-conduction law",
        "Q/t",
        base_latex="\\frac{Q}{t} = kA\\frac{\\Delta T}{L}",
    ),
)
