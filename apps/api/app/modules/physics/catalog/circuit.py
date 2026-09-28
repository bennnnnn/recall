"""Verified circuit operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("voltage", "circuit", "Ohm's law", "V", base_latex="V = IR"),
    formula("current", "circuit", "Ohm's law", "I", base_latex="V = IR"),
    formula("resistance", "circuit", "Ohm's law", "R", base_latex="V = IR"),
    formula("electrical_power", "circuit", "Electrical-power formula", "P", base_latex="P = VI"),
    formula("series_resistance", "circuit", "Series-resistance law", "R_s"),
    formula("parallel_resistance", "circuit", "Parallel-resistance law", "R_p"),
    formula("charge", "circuit", "Charge-current relation", "Q"),
    formula("electrical_energy", "circuit", "Electrical-energy formula", "E"),
    formula("capacitance", "circuit", "Capacitance formula", "C"),
    formula(
        "parallel_plate_capacitance",
        "circuit",
        "Parallel-plate capacitance",
        "C",
        base_latex="C = \\frac{\\epsilon_0A}{d}",
    ),
    formula(
        "capacitor_energy", "circuit", "Capacitor energy", "U", base_latex="U = \\frac{1}{2}CV^2"
    ),
    formula("rc_time_constant", "circuit", "RC time constant", "\\tau", base_latex="\\tau = RC"),
    formula("terminal_voltage", "circuit", "Terminal-voltage equation", "V_{terminal}"),
)
