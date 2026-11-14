"""Formulas no compound has: a metal of one charge and an anion whose charges cannot cancel.

"What is the molar mass of NaCl3?" was answered 129.34 g/mol, verified (audit 2026-11-13). A
molar mass is a sum of atomic masses, so it exists for any string of symbols; the compound does
not. Sodium is only ever Na⁺ in a compound and chlorine's anion with it is Cl⁻, so their charges
cancel only as NaCl. An answer about a compound that cannot exist declines.

Only a formula certainly impossible is refused: two elements, one a metal with a single charge
(groups 1 and 2, aluminium, zinc) and the other an element whose anions this table knows. An
anion may be a chain of atoms (O₂²⁻ in Na2O2, O₂⁻ in KO2, I₃⁻ in KI3, N₃⁻ in NaN3, S₂²⁻), and a
compound may mix them, so each element has a range of charge per atom and the metal's charge
must fall inside it. A covalent formula (PCl5, SF6, CO, H2O2), a metal of several charges
(Fe3O4, CuCl), a carbide or boride (CaC2, MgB2) and anything with three elements or more is
never refused here. Silver is left out: AgF2 and AgF3 are real.
"""

from __future__ import annotations

from fractions import Fraction

from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.formula import parse_formula

# A metal of one charge, besides groups 1 and 2.
_FIXED_CHARGES = {"Al": 3, "Zn": 2}
# The negative charge an atom of each element carries in its anions with such a metal, lowest
# to highest. Fluoride and chloride are F⁻ and Cl⁻ alone; oxygen runs from ozonide O₃⁻ to oxide
# O²⁻ and bromine from tribromide Br₃⁻ to Br⁻. Iodine, the chalcogens and the pnictogens form
# long chains (I₃⁻ to I₉⁻, S₂²⁻ to S₈²⁻, N₃⁻, N₅⁻), so only their single-atom ion bounds them.
_ANION_CHARGE: dict[str, tuple[Fraction, Fraction]] = {
    "H": (Fraction(1), Fraction(1)),
    "F": (Fraction(1), Fraction(1)),
    "Cl": (Fraction(1), Fraction(1)),
    "Br": (Fraction(1, 3), Fraction(1)),
    "I": (Fraction(0), Fraction(1)),
    "O": (Fraction(1, 3), Fraction(2)),
    "S": (Fraction(0), Fraction(2)),
    "Se": (Fraction(0), Fraction(2)),
    "Te": (Fraction(0), Fraction(2)),
    "N": (Fraction(0), Fraction(3)),
    "P": (Fraction(0), Fraction(3)),
}
# A charged formula is an ion, not a compound: "Cl3-", "SO4^2-".
_CHARGE_SIGNS = frozenset("+-^")


def _fixed_charge(symbol: str) -> int | None:
    element = BY_SYMBOL.get(symbol)
    if element is None or symbol == "H":
        return None
    if element.group in (1, 2):
        return element.group
    return _FIXED_CHARGES.get(symbol)


def impossible_compound(formula: str) -> bool:
    """Whether ``formula`` is a metal of one charge and an anion whose charges cannot cancel."""
    if _CHARGE_SIGNS.intersection(formula):
        return False
    atoms = parse_formula(formula)
    if not atoms or len(atoms) != 2:
        return False
    (first, first_count), (second, second_count) = atoms.items()
    for metal, metals, anion, anions in (
        (first, first_count, second, second_count),
        (second, second_count, first, first_count),
    ):
        charge = _fixed_charge(metal)
        per_atom = _ANION_CHARGE.get(anion)
        if charge is not None and per_atom is not None:
            low, high = per_atom
            return not low * anions <= charge * metals <= high * anions
    return False
