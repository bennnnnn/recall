"""Verified thermal operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, FormulaVariant, formula, var

# Shared with the solver so the direct-reply lines and the stored formulas stay the same.
HEAVY_PISTON_EQUATIONS: tuple[str, ...] = (
    r"P_1 = P_0 + \frac{Mg}{A}",
    r"V_1 = \frac{nRT_0}{P_1}",
    r"T_2 = T_0 \frac{V_2}{V_1}",
    r"W = nR(T_2 - T_0)",
    r"Q = nC_P(T_2 - T_0)",
    r"P_3 = P_0 - \frac{Mg}{A}",
    r"V_3 = \frac{nRT_0}{P_3}",
)
_PISTON_REST = ("frictionless piston",)
_PISTON_HEAT = ("frictionless piston", "quasi-static isobaric heating")
_PISTON_FLIP = (
    "frictionless piston",
    "inverted equilibrium is at the original temperature",
)
_PISTON_BOTH = (
    "frictionless piston",
    "quasi-static isobaric heating",
    "inverted equilibrium is at the original temperature",
)


def _piston_lines(*indexes: int) -> tuple[str, ...]:
    return tuple(HEAVY_PISTON_EQUATIONS[index] for index in indexes)


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
        "heavy_piston",
        "thermal",
        "Heavy-piston equilibrium",
        "P_1",
        base_latex=HEAVY_PISTON_EQUATIONS[0],
        assumptions=_PISTON_REST,
        variants=(
            FormulaVariant(
                lines=HEAVY_PISTON_EQUATIONS,
                present=frozenset({"upright", "expand_ratio", "cv_over_r", "flip"}),
                equals=(("expand_ratio", 2.0),),
                assumptions=_PISTON_BOTH,
                result_symbol=r"P_1,\ V_1,\ T_2,\ W,\ Q,\ P_3,\ V_3",
            ),
            FormulaVariant(
                lines=HEAVY_PISTON_EQUATIONS[:5],
                present=frozenset({"upright", "expand_ratio", "cv_over_r"}),
                absent=frozenset({"flip"}),
                equals=(("expand_ratio", 2.0),),
                assumptions=_PISTON_HEAT,
                result_symbol=r"P_1,\ V_1,\ T_2,\ W,\ Q",
            ),
            FormulaVariant(
                lines=_piston_lines(0, 1, 2, 3, 5, 6),
                present=frozenset({"upright", "expand_ratio", "flip"}),
                absent=frozenset({"cv_over_r"}),
                equals=(("expand_ratio", 2.0),),
                assumptions=_PISTON_BOTH,
                result_symbol=r"P_1,\ V_1,\ T_2,\ W,\ P_3,\ V_3",
            ),
            FormulaVariant(
                lines=HEAVY_PISTON_EQUATIONS[:4],
                present=frozenset({"upright", "expand_ratio"}),
                absent=frozenset({"cv_over_r", "flip"}),
                equals=(("expand_ratio", 2.0),),
                assumptions=_PISTON_HEAT,
                result_symbol=r"P_1,\ V_1,\ T_2,\ W",
            ),
            FormulaVariant(
                lines=_piston_lines(0, 1, 5, 6),
                present=frozenset({"upright", "flip"}),
                absent=frozenset({"expand_ratio"}),
                assumptions=_PISTON_FLIP,
                result_symbol=r"P_1,\ V_1,\ P_3,\ V_3",
            ),
            FormulaVariant(
                lines=HEAVY_PISTON_EQUATIONS[:2],
                present=frozenset({"upright"}),
                absent=frozenset({"expand_ratio", "flip"}),
                assumptions=_PISTON_REST,
                result_symbol=r"P_1,\ V_1",
            ),
            FormulaVariant(
                lines=HEAVY_PISTON_EQUATIONS[5:],
                present=frozenset({"flip"}),
                absent=frozenset({"upright"}),
                assumptions=_PISTON_FLIP,
                result_symbol=r"P_3,\ V_3",
            ),
        ),
        variables=(
            var("moles", "n", "mole"),
            var("M", "M", "kilogram"),
            var("area", "A", "meter ** 2"),
            var("p_atm", "P_0", "pascal"),
            var("temp", "T_0", "kelvin"),
            var("g", "g", "meter / second ** 2"),
            var("gas_r", "R", "joule / mole / kelvin"),
            var("expand_ratio", "V_2/V_1", dimensionless=True, visible=False),
            var("cv_over_r", "C_V/R", dimensionless=True, visible=False),
            var("upright", "upright", dimensionless=True, visible=False),
            var("flip", "flip", dimensionless=True, visible=False),
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
