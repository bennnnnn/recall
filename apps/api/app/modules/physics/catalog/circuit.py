"""Verified circuit operations."""

from __future__ import annotations

from app.services.law_binding.spec import FormulaSpec, bind, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "voltage",
        "circuit",
        "Ohm's law",
        "V",
        base_latex="V = IR",
        variables=(
            var("I", "I", "ampere"),
            var("R", "R", "ohm"),
        ),
    ),
    formula(
        "current",
        "circuit",
        "Ohm's law",
        "I",
        base_latex="V = IR",
        variables=(
            var("R", "R", "ohm"),
            var("V", "V", "volt"),
        ),
    ),
    formula(
        "resistance",
        "circuit",
        "Ohm's law",
        "R",
        base_latex="V = IR",
        variables=(
            var("I", "I", "ampere"),
            var("V", "V", "volt"),
        ),
    ),
    formula(
        "electrical_power",
        "circuit",
        "Electrical-power formula",
        "P",
        base_latex="P = VI",
        variables=(
            var("I", "I", "ampere"),
            var("R", "R", "ohm"),
            var("V", "V", "volt"),
        ),
    ),
    formula(
        "series_resistance",
        "circuit",
        "Series-resistance law",
        "R_s",
        variables=(
            var("R1", "R_1", "ohm"),
            var("R2", "R_2", "ohm"),
            var("R3", "R_3", "ohm"),
        ),
    ),
    formula(
        "parallel_resistance",
        "circuit",
        "Parallel-resistance law",
        "R_p",
        variables=(
            var("R1", "R_1", "ohm"),
            var("R2", "R_2", "ohm"),
            var("R3", "R_3", "ohm"),
        ),
    ),
    formula(
        "charge",
        "circuit",
        "Charge-current relation",
        "Q",
        variables=(
            var("I", "I", "ampere"),
            var("t", "t", "second"),
        ),
        binding=bind(("charge",), "coulomb", "I", "t"),
    ),
    formula(
        "electrical_energy",
        "circuit",
        "Electrical-energy formula",
        "E",
        variables=(
            var("power", "P", "watt"),
            var("t", "t", "second"),
        ),
    ),
    formula(
        "terminal_voltage",
        "circuit",
        "Terminal-voltage equation",
        "V_{terminal}",
        variables=(
            var("E_emf", r"\mathcal{E}", "volt"),
            var("I", "I", "ampere"),
            var("r_int", "r", "ohm"),
        ),
    ),
    formula(
        "kirchhoff_junction",
        "circuit",
        "Kirchhoff's junction rule",
        "I",
        base_latex=r"\sum I_{\mathrm{in}} = \sum I_{\mathrm{out}}",
        assumptions=("one junction and steady current",),
        variables=(
            var("i_enter", r"I_{\mathrm{in}}", "ampere"),
            var("i_leave", r"I_{\mathrm{out}}", "ampere"),
        ),
    ),
    formula(
        "kirchhoff_loop",
        "circuit",
        "Kirchhoff's loop rule",
        "I",
        base_latex=r"\sum \Delta V = 0",
        assumptions=("one battery and one series loop",),
        variables=(
            var("R1", "R_1", "ohm"),
            var("R2", "R_2", "ohm"),
            var("R3", "R_3", "ohm"),
            var("R4", "R_4", "ohm"),
            var("V", "V", "volt"),
        ),
    ),
    formula(
        "current_from_charge",
        "circuit",
        "Charge-current relation",
        "I",
        base_latex="Q = It",
        expression="Q/t",
        variables=(var("Q", "Q", "coulomb"), var("t", "t", "second")),
        binding=bind(("current",), "ampere", "Q", "t"),
    ),
    formula(
        "resistivity_resistance",
        "circuit",
        "Resistivity equation",
        "R",
        base_latex=r"R = \frac{\rho L}{A}",
        assumptions=("a uniform conductor",),
        expression="resistivity*L/area",
        variables=(
            var("L", "L", "meter"),
            var("area", "A", "meter ** 2"),
            var("resistivity", r"\rho", "ohm * meter"),
        ),
        binding=bind(("resistance",), "ohm", "L", "area", "resistivity"),
    ),
    formula(
        "transformer_voltage",
        "circuit",
        "Ideal transformer equation",
        "V_s",
        base_latex=r"\frac{V_s}{V_p} = \frac{N_s}{N_p}",
        assumptions=("an ideal transformer",),
        expression="v_primary*turns_secondary/turns_primary",
        variables=(
            var("turns_primary", "N_p", dimensionless=True, words=("primary",)),
            var("turns_secondary", "N_s", dimensionless=True, words=("secondary",)),
            var("v_primary", "V_p", "volt"),
        ),
        binding=bind(
            ("secondary voltage", "output voltage", "voltage"),
            "volt",
            "turns_primary",
            "turns_secondary",
            "v_primary",
            cues=("transformer",),
        ),
    ),
)
