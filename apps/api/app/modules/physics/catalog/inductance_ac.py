"""Verified inductor and alternating-current operations."""

from __future__ import annotations

from app.services.law_binding.spec import FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "inductor_emf",
        "circuit",
        "Inductor emf",
        r"|\mathcal{E}|",
        base_latex=r"|\mathcal{E}| = L\frac{|\Delta I|}{\Delta t}",
        assumptions=("magnitude; the minus sign is direction",),
        variables=(
            var("delta_i", r"\Delta I", "ampere"),
            var("dt", r"\Delta t", "second"),
            var("inductance", "L", "henry"),
        ),
    ),
    formula(
        "inductor_energy",
        "circuit",
        "Inductor energy",
        "U",
        base_latex=r"U = \frac{1}{2}LI^2",
        variables=(
            var("I", "I", "ampere"),
            var("inductance", "L", "henry"),
        ),
    ),
    formula(
        "rl_time_constant",
        "circuit",
        "RL time constant",
        r"\tau",
        base_latex=r"\tau = \frac{L}{R}",
        variables=(
            var("R", "R", "ohm"),
            var("inductance", "L", "henry"),
        ),
    ),
    formula(
        "rl_growth",
        "circuit",
        "RL current growth",
        "I",
        base_latex=r"I = \frac{V}{R}(1-e^{-tR/L})",
        assumptions=("current is zero before the switch closes",),
        variables=(
            var("R", "R", "ohm"),
            var("V", "V", "volt"),
            var("inductance", "L", "henry"),
            var("t", "t", "second"),
        ),
    ),
    formula(
        "rl_decay",
        "circuit",
        "RL current decay",
        "I",
        base_latex=r"I = I_0 e^{-Rt/L}",
        assumptions=("the source is removed at t = 0",),
        variables=(
            var("I0", "I_0", "ampere"),
            var("R", "R", "ohm"),
            var("inductance", "L", "henry"),
            var("t", "t", "second"),
        ),
    ),
    formula(
        "rms_voltage",
        "circuit",
        "RMS voltage",
        "V_{rms}",
        base_latex=r"V_{\mathrm{rms}} = \frac{V_0}{\sqrt{2}}",
        assumptions=("sinusoidal voltage",),
        variables=(
            var("V", "V", "volt"),
            var("to_peak", "to_peak", dimensionless=True, visible=False),
        ),
        variants=(
            FormulaVariant(
                present=frozenset({"to_peak"}),
                latex=r"V_0 = V_{\mathrm{rms}}\sqrt{2}",
                result_symbol="V_0",
            ),
        ),
    ),
    formula(
        "rms_current",
        "circuit",
        "RMS current",
        "I_{rms}",
        base_latex=r"I_{\mathrm{rms}} = \frac{I_0}{\sqrt{2}}",
        assumptions=("sinusoidal current",),
        variables=(
            var("I", "I", "ampere"),
            var("to_peak", "to_peak", dimensionless=True, visible=False),
        ),
        variants=(
            FormulaVariant(
                present=frozenset({"to_peak"}),
                latex=r"I_0 = I_{\mathrm{rms}}\sqrt{2}",
                result_symbol="I_0",
            ),
        ),
    ),
    formula(
        "inductive_reactance",
        "circuit",
        "Inductive reactance",
        "X_L",
        base_latex=r"X_L = 2\pi f L",
        variables=(
            var("freq", "f", "hertz"),
            var("inductance", "L", "henry"),
        ),
    ),
    formula(
        "capacitive_reactance",
        "circuit",
        "Capacitive reactance",
        "X_C",
        base_latex=r"X_C = \frac{1}{2\pi f C}",
        variables=(
            var("capacitance", "C", "farad"),
            var("freq", "f", "hertz"),
        ),
    ),
    formula(
        "series_impedance",
        "circuit",
        "Series impedance",
        "Z",
        base_latex=r"Z = \sqrt{R^2+(X_L-X_C)^2}",
        assumptions=("series RLC",),
        variables=(
            var("R", "R", "ohm"),
            var("capacitance", "C", "farad"),
            var("freq", "f", "hertz"),
            var("inductance", "L", "henry"),
            var("reactance_c", "X_C", "ohm"),
            var("reactance_l", "X_L", "ohm"),
        ),
    ),
    formula(
        "lc_resonance",
        "circuit",
        "LC resonance",
        "f",
        base_latex=r"f = \frac{1}{2\pi\sqrt{LC}}",
        variables=(
            var("capacitance", "C", "farad"),
            var("inductance", "L", "henry"),
        ),
    ),
    formula(
        "ac_average_power",
        "circuit",
        "Average AC power",
        "P",
        base_latex="P = I^2 R",
        assumptions=("average power in the resistor",),
        variables=(
            var("I", "I", "ampere"),
            var("R", "R", "ohm"),
        ),
    ),
)
