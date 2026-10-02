"""Verified thermal operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "heat_energy",
        "thermal",
        "Specific-heat equation",
        "Q",
        variables=(
            var("c_heat", "c", "joule / kilogram / kelvin"),
            var("delta_temp", r"\Delta T", "kelvin"),
            var("m", "m", "kilogram"),
            # "from 20 °C to 80 °C": both readings, so the working shows ΔT.
            var("temp_initial", "T_1", "kelvin"),
            var("temp_final", "T_2", "kelvin"),
        ),
    ),
    formula(
        "ideal_gas_pressure",
        "thermal",
        "Ideal-gas law",
        "P",
        base_latex="PV = nRT",
        variables=(
            var("moles", "n", "mole"),
            var("temp", "T", "kelvin"),
            var("volume", "V", "meter ** 3"),
        ),
    ),
    formula(
        "ideal_gas_volume",
        "thermal",
        "Ideal-gas law",
        "V",
        base_latex="PV = nRT",
        variables=(
            var("moles", "n", "mole"),
            var("pres", "P", "pascal"),
            var("temp", "T", "kelvin"),
        ),
    ),
    formula(
        "ideal_gas_amount",
        "thermal",
        "Ideal-gas law",
        "n",
        base_latex="PV = nRT",
        variables=(
            var("pres", "P", "pascal"),
            var("temp", "T", "kelvin"),
            var("volume", "V", "meter ** 3"),
        ),
    ),
    formula(
        "ideal_gas_temperature",
        "thermal",
        "Ideal-gas law",
        "T",
        base_latex="PV = nRT",
        variables=(
            var("moles", "n", "mole"),
            var("pres", "P", "pascal"),
            var("volume", "V", "meter ** 3"),
        ),
    ),
    formula(
        "monatomic_energy",
        "thermal",
        "Monatomic internal energy",
        "U",
        base_latex=r"U = \frac{3}{2}nRT",
        assumptions=("monatomic ideal gas",),
        variables=(
            var("moles", "n", "mole"),
            var("temp", "T", "kelvin"),
        ),
    ),
    formula(
        "isobaric_work",
        "thermal",
        "Isobaric work",
        "W",
        base_latex=r"W = P\Delta V",
        assumptions=("work done by the gas",),
        variables=(
            var("pres", "P", "pascal"),
            var("vol1", "V_1", "meter ** 3"),
            var("vol2", "V_2", "meter ** 3"),
        ),
    ),
    formula(
        "adiabatic_pressure",
        "thermal",
        "Adiabatic condition",
        "P_2",
        base_latex=r"P_1 V_1^\gamma = P_2 V_2^\gamma",
        assumptions=("reversible adiabatic process with gamma stated",),
        variables=(
            var("gamma_gas", r"\gamma", dimensionless=True),
            var("pres1", "P_1", "pascal"),
            var("vol1", "V_1", "meter ** 3"),
            var("vol2", "V_2", "meter ** 3"),
        ),
    ),
    formula(
        "adiabatic_volume",
        "thermal",
        "Adiabatic condition",
        "V_2",
        base_latex=r"P_1 V_1^\gamma = P_2 V_2^\gamma",
        assumptions=("reversible adiabatic process with gamma stated",),
        variables=(
            var("gamma_gas", r"\gamma", dimensionless=True),
            var("pres1", "P_1", "pascal"),
            var("pres2", "P_2", "pascal"),
            var("vol1", "V_1", "meter ** 3"),
        ),
    ),
    formula(
        "refrigerator_cop",
        "thermal",
        "Refrigerator coefficient of performance",
        "COP",
        base_latex=r"COP = \frac{T_C}{T_H - T_C}",
        assumptions=("Carnot refrigerator, absolute temperatures",),
        variables=(
            var("temp", "T", "kelvin"),
            var("temp_env", "T_C", "kelvin"),
        ),
    ),
    formula(
        "heat_pump_cop",
        "thermal",
        "Heat-pump coefficient of performance",
        "COP",
        base_latex=r"COP = \frac{T_H}{T_H - T_C}",
        assumptions=("Carnot heat pump, absolute temperatures",),
        variables=(
            var("temp", "T", "kelvin"),
            var("temp_env", "T_C", "kelvin"),
        ),
    ),
    formula(
        "thermal_efficiency",
        "thermal",
        "Thermal-efficiency formula",
        "\\eta",
        variables=(
            var("Q_in", r"Q_{\mathrm{in}}", "joule"),
            var("W_out", r"W_{\mathrm{out}}", "joule"),
        ),
    ),
    formula(
        "linear_expansion",
        "thermal",
        "Linear thermal-expansion law",
        "\\Delta L",
        base_latex="\\Delta L = \\alpha L_0\\Delta T",
        variables=(
            var("L0", "L_0", "meter"),
            var("alpha", r"\alpha", "1 / kelvin"),
            var("delta_temp", r"\Delta T", "kelvin"),
        ),
    ),
    formula(
        "latent_heat",
        "thermal",
        "Latent-heat equation",
        "Q",
        base_latex="Q = mL",
        variables=(
            var("latent_heat", "L", "joule / kilogram"),
            var("m", "m", "kilogram"),
        ),
    ),
    formula(
        "first_law_internal_energy",
        "thermal",
        "First law of thermodynamics",
        "\\Delta U",
        base_latex="\\Delta U = Q - W",
        variables=(
            var("W", "W", "joule"),
            var("heat", "Q", "joule"),
        ),
    ),
    formula(
        "carnot_efficiency",
        "thermal",
        "Carnot-efficiency equation",
        "\\eta_C",
        base_latex="\\eta_C = 1 - \\frac{T_C}{T_H}",
        variables=(
            var("temp", "T_H", "kelvin"),
            var("temp_env", "T_C", "kelvin"),
        ),
    ),
    formula(
        "entropy_change",
        "thermal",
        "Entropy-change equation",
        "\\Delta S",
        base_latex="\\Delta S = \\frac{Q_{rev}}{T}",
        variables=(
            var("heat", "Q", "joule"),
            var("temp", "T", "kelvin"),
        ),
    ),
    formula(
        "heat_conduction_rate",
        "thermal",
        "Fourier heat-conduction law",
        "Q/t",
        base_latex="\\frac{Q}{t} = kA\\frac{\\Delta T}{L}",
        variables=(
            var("L", "L", "meter"),
            var("area", "A", "meter ** 2"),
            var("delta_temp", r"\Delta T", "kelvin"),
            var("thermal_conductivity", "k", "watt / meter / kelvin"),
        ),
    ),
)
