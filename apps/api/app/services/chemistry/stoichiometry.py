"""Stoichiometry, molar mass, and periodic-table helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.chemistry.equations import _parse_formula_atoms, balance_equation
from app.services.chemistry.smiles import validate_smiles


@dataclass(frozen=True)
class StoichiometryResult:
    """Result of a stoichiometry calculation."""

    answer: str  # human-readable answer
    limiting_reagent: str | None = None
    product_amount: float | None = None
    error: str | None = None


def stoichiometry(
    equation: str,
    known_reactant: str,
    known_amount: float,
    target_product: str | None = None,
) -> StoichiometryResult:
    """Calculate product yield from a balanced equation and known reactant amount.

    If target_product is None, uses the first product.
    """
    balanced = balance_equation(equation)
    if not balanced.balanced:
        return StoichiometryResult("", error=balanced.error)

    if known_reactant not in balanced.reactants:
        return StoichiometryResult("", error=f"{known_reactant} not found in reactants")

    reactant_coeff = balanced.reactants[known_reactant]

    if target_product is None:
        target_product = next(iter(balanced.products))
    if target_product not in balanced.products:
        return StoichiometryResult("", error=f"{target_product} not found in products")

    product_coeff = balanced.products[target_product]
    # Mole ratio: product_coeff / reactant_coeff
    product_amount = known_amount * product_coeff / reactant_coeff
    answer = (
        f"{known_amount} mol {known_reactant} produces {product_amount:.4g} mol {target_product}"
    )
    return StoichiometryResult(
        answer=answer,
        product_amount=product_amount,
    )


_SMILES_ONLY_CHARS = frozenset("=#[@]")


def _mass_from_hill(atoms: dict[str, int]) -> float | None:
    """Sum atomic masses. None when any symbol is missing from the table."""
    total = 0.0
    for elem, count in atoms.items():
        info = PERIODIC_TABLE.get(elem)
        if info is None:
            return None
        mass = info.get("mass")
        if not isinstance(mass, int | float):
            return None
        total += float(mass) * count
    return round(total, 2)


def _prefer_smiles(raw: str) -> bool:
    """True for organic SMILES that a Hill parse would misread (``CCO`` → C₂O)."""
    if any(ch in _SMILES_ONLY_CHARS for ch in raw):
        return True
    letters = sum(1 for ch in raw if ch.isalpha())
    if letters >= 3 and not any(ch.isdigit() for ch in raw):
        atoms = _parse_formula_atoms(raw)
        if atoms and all(len(elem) == 1 for elem in atoms):
            return True
    return False


def molar_mass(formula_or_smiles: str) -> float:
    """Calculate the molar mass of a compound from its formula or SMILES.

    Hill formulas (``CO``, ``C``, ``H2O``) are summed from the element table so
    RDKit cannot saturate them into hydrides (methanol / methane). Organic
    SMILES such as ``CCO`` still go through RDKit.
    """
    cleaned = formula_or_smiles.strip()
    if not cleaned:
        raise ValueError("cannot compute molar mass for empty string")

    hill_atoms = _parse_formula_atoms(cleaned)
    if hill_atoms and not _prefer_smiles(cleaned):
        mass = _mass_from_hill(hill_atoms)
        if mass is not None:
            return mass

    props = validate_smiles(cleaned)
    if props.valid:
        return props.molecular_weight

    if hill_atoms:
        mass = _mass_from_hill(hill_atoms)
        if mass is not None:
            return mass
    raise ValueError(f"cannot compute molar mass for {formula_or_smiles}")


PERIODIC_TABLE: dict[str, dict[str, float | int | str]] = {
    "H": {"mass": 1.008, "electronegativity": 2.20, "group": 1, "period": 1, "name": "Hydrogen"},
    "He": {"mass": 4.003, "group": 18, "period": 1, "name": "Helium"},
    "Li": {"mass": 6.941, "electronegativity": 0.98, "group": 1, "period": 2, "name": "Lithium"},
    "Be": {"mass": 9.012, "electronegativity": 1.57, "group": 2, "period": 2, "name": "Beryllium"},
    "B": {"mass": 10.811, "electronegativity": 2.04, "group": 13, "period": 2, "name": "Boron"},
    "C": {"mass": 12.011, "electronegativity": 2.55, "group": 14, "period": 2, "name": "Carbon"},
    "N": {"mass": 14.007, "electronegativity": 3.04, "group": 15, "period": 2, "name": "Nitrogen"},
    "O": {"mass": 15.999, "electronegativity": 3.44, "group": 16, "period": 2, "name": "Oxygen"},
    "F": {"mass": 18.998, "electronegativity": 3.98, "group": 17, "period": 2, "name": "Fluorine"},
    "Ne": {"mass": 20.180, "group": 18, "period": 2, "name": "Neon"},
    "Na": {"mass": 22.990, "electronegativity": 0.93, "group": 1, "period": 3, "name": "Sodium"},
    "Mg": {"mass": 24.305, "electronegativity": 1.31, "group": 2, "period": 3, "name": "Magnesium"},
    "Al": {
        "mass": 26.982,
        "electronegativity": 1.61,
        "group": 13,
        "period": 3,
        "name": "Aluminum",
    },
    "Si": {"mass": 28.085, "electronegativity": 1.90, "group": 14, "period": 3, "name": "Silicon"},
    "P": {
        "mass": 30.974,
        "electronegativity": 2.19,
        "group": 15,
        "period": 3,
        "name": "Phosphorus",
    },
    "S": {"mass": 32.06, "electronegativity": 2.58, "group": 16, "period": 3, "name": "Sulfur"},
    "Cl": {"mass": 35.45, "electronegativity": 3.16, "group": 17, "period": 3, "name": "Chlorine"},
    "Ar": {"mass": 39.948, "group": 18, "period": 3, "name": "Argon"},
    "K": {"mass": 39.098, "electronegativity": 0.82, "group": 1, "period": 4, "name": "Potassium"},
    "Ca": {"mass": 40.078, "electronegativity": 1.00, "group": 2, "period": 4, "name": "Calcium"},
    "Ti": {"mass": 47.867, "electronegativity": 1.54, "group": 4, "period": 4, "name": "Titanium"},
    "Cr": {"mass": 51.996, "electronegativity": 1.66, "group": 6, "period": 4, "name": "Chromium"},
    "Mn": {"mass": 54.938, "electronegativity": 1.55, "group": 7, "period": 4, "name": "Manganese"},
    "Fe": {"mass": 55.845, "electronegativity": 1.83, "group": 8, "period": 4, "name": "Iron"},
    "Co": {"mass": 58.933, "electronegativity": 1.88, "group": 9, "period": 4, "name": "Cobalt"},
    "Ni": {"mass": 58.693, "electronegativity": 1.91, "group": 10, "period": 4, "name": "Nickel"},
    "Cu": {"mass": 63.546, "electronegativity": 1.90, "group": 11, "period": 4, "name": "Copper"},
    "Zn": {"mass": 65.38, "electronegativity": 1.65, "group": 12, "period": 4, "name": "Zinc"},
    "Ga": {"mass": 69.723, "electronegativity": 1.81, "group": 13, "period": 4, "name": "Gallium"},
    "Ge": {"mass": 72.63, "electronegativity": 2.01, "group": 14, "period": 4, "name": "Germanium"},
    "As": {"mass": 74.922, "electronegativity": 2.18, "group": 15, "period": 4, "name": "Arsenic"},
    "Se": {"mass": 78.96, "electronegativity": 2.55, "group": 16, "period": 4, "name": "Selenium"},
    "Br": {"mass": 79.904, "electronegativity": 2.96, "group": 17, "period": 4, "name": "Bromine"},
    "Rb": {"mass": 85.468, "electronegativity": 0.82, "group": 1, "period": 5, "name": "Rubidium"},
    "Sr": {"mass": 87.62, "electronegativity": 0.95, "group": 2, "period": 5, "name": "Strontium"},
    "Mo": {"mass": 95.95, "electronegativity": 2.16, "group": 6, "period": 5, "name": "Molybdenum"},
    "Cd": {"mass": 112.41, "electronegativity": 1.69, "group": 12, "period": 5, "name": "Cadmium"},
    "Sn": {"mass": 118.71, "electronegativity": 1.96, "group": 14, "period": 5, "name": "Tin"},
    "Sb": {"mass": 121.76, "electronegativity": 2.05, "group": 15, "period": 5, "name": "Antimony"},
    "I": {"mass": 126.904, "electronegativity": 2.66, "group": 17, "period": 5, "name": "Iodine"},
    "Cs": {"mass": 132.91, "electronegativity": 0.79, "group": 1, "period": 6, "name": "Cesium"},
    "Ba": {"mass": 137.327, "electronegativity": 0.89, "group": 2, "period": 6, "name": "Barium"},
    "W": {"mass": 183.84, "electronegativity": 2.36, "group": 6, "period": 6, "name": "Tungsten"},
    "Pt": {"mass": 195.08, "electronegativity": 2.28, "group": 10, "period": 6, "name": "Platinum"},
    "Au": {"mass": 196.967, "electronegativity": 2.54, "group": 11, "period": 6, "name": "Gold"},
    "Hg": {"mass": 200.59, "electronegativity": 2.00, "group": 12, "period": 6, "name": "Mercury"},
    "Pb": {"mass": 207.2, "electronegativity": 2.33, "group": 14, "period": 6, "name": "Lead"},
    "Bi": {"mass": 208.98, "electronegativity": 2.02, "group": 15, "period": 6, "name": "Bismuth"},
    "U": {"mass": 238.03, "electronegativity": 1.38, "group": 3, "period": 7, "name": "Uranium"},
    "Ag": {"mass": 107.868, "electronegativity": 1.93, "group": 11, "period": 5, "name": "Silver"},
}


def get_element_info(symbol: str) -> dict[str, float | int | str] | None:
    """Get periodic table data for an element by symbol.

    Returns None if the element is not in our data.
    """
    return PERIODIC_TABLE.get(symbol)


@dataclass(frozen=True)
class LimitingReagentResult:
    """Result of a limiting reagent calculation."""

    answer: str
    limiting_reagent: str | None = None
    product_amount: float | None = None
    error: str | None = None


def limiting_reagent(
    equation: str,
    reactant_amounts: dict[str, float],
    target_product: str | None = None,
) -> LimitingReagentResult:
    """Determine the limiting reagent and product yield.

    reactant_amounts maps formula → moles available.
    """
    balanced = balance_equation(equation)
    if not balanced.balanced:
        return LimitingReagentResult(answer="", error=balanced.error)

    if target_product is None:
        target_product = next(iter(balanced.products))
    if target_product not in balanced.products:
        return LimitingReagentResult(answer="", error=f"{target_product} not found in products")

    product_coeff = balanced.products[target_product]
    # For each reactant, compute how much product it could make.
    best_reactant: str | None = None
    best_product: float = float("inf")
    for reactant, amount in reactant_amounts.items():
        if reactant not in balanced.reactants:
            return LimitingReagentResult(answer="", error=f"{reactant} not found in reactants")
        r_coeff = balanced.reactants[reactant]
        possible = amount * product_coeff / r_coeff
        if possible < best_product:
            best_product = possible
            best_reactant = reactant

    return LimitingReagentResult(
        answer=(
            f"Limiting reagent: {best_reactant}. Product ({target_product}): {best_product:.4g} mol"
        ),
        limiting_reagent=best_reactant,
        product_amount=round(best_product, 4),
    )
