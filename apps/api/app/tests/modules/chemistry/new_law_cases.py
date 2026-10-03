# ruff: noqa: RUF002 -- worked answers use the multiplication sign.
"""One school question per law added after the original catalog, with its worked answer.

Each answer was checked by hand to the figures the question's data carry:
- 0.200 M × 0.500 L × 58.44 g/mol = 5.84 g;
- 3.01 × 10^23 / (6.022 × 10^23) × 18.02 g/mol = 9.00 g;
- √(32.00 / 2.016) = 3.984;
- 75.77% × 34.969 u + 24.23% × 36.966 u = 35.45 u.
"""

from __future__ import annotations

NEW_LAW_CASES: tuple[tuple[str, str, str], ...] = (
    (
        "How many grams of NaCl are needed to make 500 mL of a 0.200 M NaCl solution?",
        "solution_mass",
        "m = 5.84 g",
    ),
    (
        "What is the molality of a solution of 18.0 g of glucose dissolved in 500 g of water?",
        "molality_from_mass",
        "b = 0.200 mol/kg",
    ),
    (
        "What is the mass percent of 5.0 g of sugar dissolved in 95.0 g of water?",
        "mass_percent_solvent",
        "Mass percent = 5.0%",
    ),
    (
        "Find the mole fraction of NaCl when 1.0 mol of NaCl is dissolved in 9.0 mol of water.",
        "mole_fraction",
        "χ = 0.10",
    ),
    (
        "How many grams do 3.01 × 10^23 molecules of H2O weigh?",
        "particles_to_mass",
        "m = 9.00 g",
    ),
    ("What is the density of CO2 gas at 1.00 atm and 273 K?", "gas_density", "d = 1.96 g/L"),
    (
        "A gas has a density of 1.25 g/L at 1.00 atm and 273 K. What is its molar mass?",
        "molar_mass_from_density",
        "M = 28.0 g/mol",
    ),
    (
        "What is the percent ionization of 0.10 M acetic acid? Ka = 1.8e-5",
        "percent_ionization",
        "Percent ionization = 1.3%",
    ),
    (
        "How much heat is released when 2.00 mol of CH4 burns? ΔH = -890 kJ/mol",
        "reaction_heat",
        "q = -1780 kJ",
    ),
    (
        "How long does it take to deposit 10.0 g of Cu from Cu2+ with a current of 2.00 A?",
        "electrolysis_time",
        "t = 1.52 × 10^4 s",
    ),
    (
        "25.0 mL of NaOH is neutralized by 20.0 mL of 0.100 M HCl. "
        "Find the concentration of the NaOH.",
        "titration_concentration",
        "C₂ = 0.0800 mol/L",
    ),
    (
        "Compare the rates of effusion of H2 and O2.",
        "graham_ratio",
        "rate(H2) / rate(O2) = 3.984",
    ),
    ("How many grams of oxygen are in 10.0 g of H2O?", "element_mass", "m(O) = 8.88 g"),
    (
        "Chlorine has isotopes 35Cl (75.77%) and 37Cl (24.23%). Find its average atomic mass.",
        "average_atomic_mass",
        "A(Cl) = 35.45 u",
    ),
    (
        "What is the electron configuration of Fe?",
        "electron_configuration",
        "Fe: [Ar] 3d6 4s2",
    ),
)
