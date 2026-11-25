# ruff: noqa: RUF001 -- textbook formulas use Greek.
"""A gas's density, and a molar mass from it: physics' law, in chemistry's names and units.

The ideal-gas density is physics' (``law_binding.shared_laws``); only chemistry reads a
molar mass from the gas a question names ("the density of CO2 at STP"). These rows take the
owner's arithmetic in their own names and units (atm, g/mol, K, g/L, the gas constant in
L·atm/(mol·K)), never a copy of it.
"""

from __future__ import annotations

from app.modules.chemistry.formula_record import FormulaLaw, _law
from app.services.law_binding.shared_laws import IDEAL_GAS_DENSITY, in_names, solved_for

_GAS_NAMES = {
    "pres": "pressure",
    "temp": "temperature",
    "R_gas": "R_atm",
    "ideal_gas_density": "density",
}

GAS_DENSITY_LAWS: tuple[FormulaLaw, ...] = (
    _law(
        "gas_density",
        "gases",
        "Ideal gas density",
        "ρ = PM / RT",
        "Density, ρ",
        ("ρ", "g/L"),
        in_names(IDEAL_GAS_DENSITY.expression, _GAS_NAMES),
        (
            ("pressure", "P", "atm"),
            ("molar_mass", "M({formula})", "g/mol"),
            ("temperature", "T", "K"),
        ),
        "ρ = ({pressure})({molar_mass}) / [({R_atm})({temperature})]",
    ),
    _law(
        "molar_mass_from_density",
        "gases",
        "Ideal gas density",
        "M = ρRT / P",
        "Molar mass, M",
        ("M", "g/mol"),
        solved_for(IDEAL_GAS_DENSITY, "molar_mass", _GAS_NAMES),
        (
            ("density", "ρ", "g/L"),
            ("temperature", "T", "K"),
            ("pressure", "P", "atm"),
        ),
        "M = ({density})({R_atm})({temperature}) / {pressure}",
    ),
)
