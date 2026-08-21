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


def molar_mass(formula_or_smiles: str) -> float:
    """Calculate the molar mass of a compound from its formula or SMILES.

    Uses RDKit when the input is a valid SMILES. For plain formulas
    (e.g. "H2O", "C6H12O6"), parses the formula and sums atomic masses.
    """
    # Try SMILES first (RDKit gives exact molecular weight).
    props = validate_smiles(formula_or_smiles)
    if props.valid:
        return props.molecular_weight

    # Fall back to formula parsing with atomic masses.
    atoms = _parse_formula_atoms(formula_or_smiles)
    if not atoms:
        raise ValueError(f"cannot compute molar mass for {formula_or_smiles}")

    # Common atomic masses (g/mol).
    _ATOMIC_MASSES = {
        "H": 1.008,
        "C": 12.011,
        "N": 14.007,
        "O": 15.999,
        "F": 18.998,
        "Na": 22.990,
        "Mg": 24.305,
        "Al": 26.982,
        "Si": 28.085,
        "P": 30.974,
        "S": 32.06,
        "Cl": 35.45,
        "K": 39.098,
        "Ca": 40.078,
        "Fe": 55.845,
        "Cu": 63.546,
        "Zn": 65.38,
        "Br": 79.904,
        "I": 126.904,
        "Ba": 137.327,
        "Pb": 207.2,
        "Ag": 107.868,
        "Au": 196.967,
        "He": 4.003,
        "Li": 6.941,
        "Be": 9.012,
        "B": 10.811,
        "Ne": 20.180,
        "Ar": 39.948,
        "Ti": 47.867,
        "Cr": 51.996,
        "Mn": 54.938,
        "Co": 58.933,
        "Ni": 58.693,
        "Ga": 69.723,
        "Ge": 72.63,
        "As": 74.922,
        "Se": 78.96,
        "Sr": 87.62,
        "Sn": 118.71,
        "Sb": 121.76,
        "Bi": 208.98,
    }
    total = 0.0
    for elem, count in atoms.items():
        mass = _ATOMIC_MASSES.get(elem)
        if mass is None:
            raise ValueError(f"unknown element: {elem}")
        total += mass * count
    return round(total, 2)


PERIODIC_TABLE: dict[str, dict[str, float | int | str]] = {
    "H": {"mass": 1.008, "electronegativity": 2.20, "group": 1, "period": 1, "name": "Hydrogen"},
    "He": {"mass": 4.003, "electronegativity": 0.0, "group": 18, "period": 1, "name": "Helium"},
    "Li": {"mass": 6.941, "electronegativity": 0.98, "group": 1, "period": 2, "name": "Lithium"},
    "Be": {"mass": 9.012, "electronegativity": 1.57, "group": 2, "period": 2, "name": "Beryllium"},
    "B": {"mass": 10.811, "electronegativity": 2.04, "group": 13, "period": 2, "name": "Boron"},
    "C": {"mass": 12.011, "electronegativity": 2.55, "group": 14, "period": 2, "name": "Carbon"},
    "N": {"mass": 14.007, "electronegativity": 3.04, "group": 15, "period": 2, "name": "Nitrogen"},
    "O": {"mass": 15.999, "electronegativity": 3.44, "group": 16, "period": 2, "name": "Oxygen"},
    "F": {"mass": 18.998, "electronegativity": 3.98, "group": 17, "period": 2, "name": "Fluorine"},
    "Ne": {"mass": 20.180, "electronegativity": 0.0, "group": 18, "period": 2, "name": "Neon"},
    "Na": {"mass": 22.990, "electronegativity": 0.93, "group": 1, "period": 3, "name": "Sodium"},
    "Mg": {"mass": 24.305, "electronegativity": 1.31, "group": 2, "period": 3, "name": "Magnesium"},
    "Al": {"mass": 26.982, "electronegativity": 1.61, "group": 13, "period": 3, "name": "Aluminum"},
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
    "Ar": {"mass": 39.948, "electronegativity": 0.0, "group": 18, "period": 3, "name": "Argon"},
    "K": {"mass": 39.098, "electronegativity": 0.82, "group": 1, "period": 4, "name": "Potassium"},
    "Ca": {"mass": 40.078, "electronegativity": 1.00, "group": 2, "period": 4, "name": "Calcium"},
    "Fe": {"mass": 55.845, "electronegativity": 1.83, "group": 8, "period": 4, "name": "Iron"},
    "Cu": {"mass": 63.546, "electronegativity": 1.90, "group": 11, "period": 4, "name": "Copper"},
    "Zn": {"mass": 65.38, "electronegativity": 1.65, "group": 12, "period": 4, "name": "Zinc"},
    "Br": {"mass": 79.904, "electronegativity": 2.96, "group": 17, "period": 4, "name": "Bromine"},
    "I": {"mass": 126.904, "electronegativity": 2.66, "group": 17, "period": 5, "name": "Iodine"},
    "Ag": {"mass": 107.868, "electronegativity": 1.93, "group": 11, "period": 5, "name": "Silver"},
    "Au": {"mass": 196.967, "electronegativity": 2.54, "group": 11, "period": 6, "name": "Gold"},
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
