"""Chemistry service — RDKit-backed SMILES validation, properties, and coordinates.

Validates SMILES strings from model output, computes molecular properties
(weight, formula, atom count), and generates 2D/3D coordinates for
visualization. All work is server-side (Golden Rule 7); the mobile app
only renders verified results.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# RDKit is a heavy import (~2s cold). Defer to first use so the app starts
# fast and tests that don't need chemistry don't pay the cost.
_rdkit_loaded = False


def _ensure_rdkit() -> None:
    global _rdkit_loaded
    if _rdkit_loaded:
        return
    # Importing RDKit modules triggers the load.
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors

    _ = Chem, AllChem, Descriptors  # keep refs for mypy
    _rdkit_loaded = True


# Model output often uses formulas (`H2`, `O2`) as ```smiles bodies.
# RDKit reads those as ring-closure syntax, not diatomic molecules.
_DIATOMIC_SMILES: dict[str, str] = {
    "H-H": "[H][H]",
    "H2": "[H][H]",
    "O2": "O=O",
    "N2": "N#N",
    "F2": "FF",
    "Cl2": "ClCl",
    "Br2": "BrBr",
    "I2": "II",
}


def normalize_smiles_input(raw: str) -> str:
    """Map common diatomic formulas to SMILES RDKit can parse."""
    key = raw.strip()
    return _DIATOMIC_SMILES.get(key, key)


@dataclass(frozen=True)
class MoleculeProperties:
    """Verified molecular properties from RDKit."""

    smiles: str  # canonical SMILES
    formula: str  # molecular formula (Hill notation)
    molecular_weight: float  # g/mol
    atom_count: int  # heavy atom count (no H)
    bond_count: int
    valid: bool = True
    error: str | None = None


@dataclass(frozen=True)
class MoleculeCoordinates:
    """2D or 3D coordinates for visualization."""

    smiles: str
    # SDF (structure-data file) format for 3Dmol.js rendering.
    # Empty when coordinates could not be generated.
    sdf: str = ""
    # 2D coordinates as a list of (x, y) pairs per atom (for SVG rendering).
    coords_2d: list[tuple[float, float]] = field(default_factory=list)
    error: str | None = None


def validate_smiles(smiles: str) -> MoleculeProperties:
    """Validate a SMILES string and compute molecular properties.

    Returns MoleculeProperties with valid=False if the SMILES is invalid.
    """
    _ensure_rdkit()
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    smiles = normalize_smiles_input(smiles.strip())
    if not smiles or len(smiles) > 500:
        return MoleculeProperties(
            smiles=smiles,
            formula="",
            molecular_weight=0.0,
            atom_count=0,
            bond_count=0,
            valid=False,
            error="SMILES too long or empty",
        )

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return MoleculeProperties(
                smiles=smiles,
                formula="",
                molecular_weight=0.0,
                atom_count=0,
                bond_count=0,
                valid=False,
                error="invalid SMILES",
            )
        canonical = Chem.MolToSmiles(mol)
        formula = Chem.rdMolDescriptors.CalcMolFormula(mol)
        weight = Descriptors.MolWt(mol)  # type: ignore[attr-defined]
        atom_count = mol.GetNumAtoms()
        bond_count = mol.GetNumBonds()
        return MoleculeProperties(
            smiles=canonical,
            formula=formula,
            molecular_weight=round(weight, 2),
            atom_count=atom_count,
            bond_count=bond_count,
        )
    except Exception as exc:
        logger.info("RDKit validate failed for %r: %s", smiles, exc)
        return MoleculeProperties(
            smiles=smiles,
            formula="",
            molecular_weight=0.0,
            atom_count=0,
            bond_count=0,
            valid=False,
            error=str(exc),
        )


def generate_2d_coordinates(smiles: str) -> MoleculeCoordinates:
    """Generate 2D coordinates for SVG rendering.

    Returns MoleculeCoordinates with empty coords_2d on failure.
    """
    _ensure_rdkit()
    from rdkit import Chem
    from rdkit.Chem import AllChem

    smiles = normalize_smiles_input(smiles.strip())
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return MoleculeCoordinates(smiles=smiles, error="invalid SMILES")
        canonical = Chem.MolToSmiles(mol)
        AllChem.Compute2DCoords(mol)  # type: ignore[attr-defined]
        coords = mol.GetConformer()
        coords_2d = [
            (round(coords.GetAtomPosition(i).x, 4), round(coords.GetAtomPosition(i).y, 4))
            for i in range(mol.GetNumAtoms())
        ]
        return MoleculeCoordinates(smiles=canonical, coords_2d=coords_2d)
    except Exception as exc:
        logger.info("RDKit 2D coords failed for %r: %s", smiles, exc)
        return MoleculeCoordinates(smiles=smiles, error=str(exc))


def generate_3d_coordinates(smiles: str) -> MoleculeCoordinates:
    """Generate 3D coordinates as an SDF string for 3Dmol.js rendering.

    Uses RDKit's ETKDG method for 3D conformer generation. Returns
    MoleculeCoordinates with empty sdf on failure.
    """
    _ensure_rdkit()
    from rdkit import Chem
    from rdkit.Chem import AllChem

    smiles = normalize_smiles_input(smiles.strip())
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return MoleculeCoordinates(smiles=smiles, error="invalid SMILES")
        canonical = Chem.MolToSmiles(mol)
        mol = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()  # type: ignore[attr-defined]
        params.numThreads = 0
        params.useRandomCoords = False
        result = AllChem.EmbedMolecule(mol, params)  # type: ignore[attr-defined]
        if result != 0:
            # Fallback to the older ETKDG if v3 fails.
            result = AllChem.EmbedMolecule(mol, AllChem.ETKDG())  # type: ignore[attr-defined]
        if result != 0:
            return MoleculeCoordinates(smiles=canonical, error="3D embedding failed")
        AllChem.MMFFOptimizeMolecule(mol)  # type: ignore[attr-defined]
        mol = Chem.RemoveHs(mol)
        sdf = Chem.MolToMolBlock(mol)
        return MoleculeCoordinates(smiles=canonical, sdf=sdf)
    except Exception as exc:
        logger.info("RDKit 3D coords failed for %r: %s", smiles, exc)
        return MoleculeCoordinates(smiles=smiles, error=str(exc))


def enrich_smiles_fence(smiles: str) -> dict[str, Any]:
    """Validate a SMILES and return enriched metadata for the fence.

    Returns a dict with:
    - smiles: canonical SMILES
    - valid: bool
    - formula: molecular formula (or "")
    - molecular_weight: float (or 0)
    - atom_count: int (or 0)
    - error: str | None
    """
    props = validate_smiles(smiles)
    return {
        "smiles": props.smiles,
        "valid": props.valid,
        "formula": props.formula,
        "molecular_weight": props.molecular_weight,
        "atom_count": props.atom_count,
        "error": props.error,
    }


# ---------------------------------------------------------------------------
# Chemical equation balancing (SymPy linear algebra)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BalancedEquation:
    """Result of balancing a chemical equation."""

    reactants: dict[str, int]  # species → coefficient
    products: dict[str, int]  # species → coefficient
    balanced: bool
    error: str | None = None


def _parse_equation_side(side: str) -> list[tuple[str, int]]:
    """Parse one side of a chemical equation into (species, count) pairs.

    e.g. "2 H2 + O2" → [("H2", 2), ("O2", 1)]
    """
    terms = []
    for part in side.split("+"):
        part = part.strip()
        if not part:
            continue
        # Match optional coefficient + formula.
        match = re.match(r"^(\d*)\s*([A-Za-z0-9\(\)\[\]\.]+)$", part)
        if match is None:
            continue
        coeff = int(match.group(1)) if match.group(1) else 1
        formula = match.group(2)
        terms.append((formula, coeff))
    return terms


def _parse_formula_atoms(formula: str) -> dict[str, int]:
    """Parse a chemical formula into element → count.

    e.g. "H2O" → {"H": 2, "O": 1}, "C6H12O6" → {"C": 6, "H": 12, "O": 6}
    Handles parentheses: "Ca(OH)2" → {"Ca": 1, "O": 2, "H": 2}
    """
    atoms: dict[str, int] = {}

    def _parse(s: str, multiplier: int = 1) -> None:
        i = 0
        while i < len(s):
            if s[i] == "(" or s[i] == "[":
                # Find matching close paren.
                depth = 1
                j = i + 1
                while j < len(s) and depth > 0:
                    if s[j] in "([":
                        depth += 1
                    elif s[j] in ")]":
                        depth -= 1
                    if depth == 0:
                        break
                    j += 1
                inner = s[i + 1 : j]
                # Check for multiplier after close paren.
                k = j + 1
                num_str = ""
                while k < len(s) and s[k].isdigit():
                    num_str += s[k]
                    k += 1
                inner_mult = int(num_str) if num_str else 1
                _parse(inner, multiplier * inner_mult)
                i = k
            elif s[i].isupper():
                # Element symbol.
                elem = s[i]
                j = i + 1
                while j < len(s) and s[j].islower():
                    elem += s[j]
                    j += 1
                # Check for count.
                num_str = ""
                while j < len(s) and s[j].isdigit():
                    num_str += s[j]
                    j += 1
                count = int(num_str) if num_str else 1
                atoms[elem] = atoms.get(elem, 0) + count * multiplier
                i = j
            else:
                i += 1

    _parse(formula)
    return atoms


def balance_equation(equation: str) -> BalancedEquation:
    """Balance a chemical equation using SymPy linear algebra.

    e.g. "H2 + O2 -> H2O" → reactants={"H2": 2, "O2": 1}, products={"H2O": 2}
    """
    _ensure_rdkit()  # not needed, but keeps the lazy-load pattern
    from sympy import Matrix, lcm

    if "->" not in equation and "→" not in equation:
        return BalancedEquation({}, {}, False, "no arrow in equation")
    arrow = "->" if "->" in equation else "→"
    left, right = equation.split(arrow, 1)

    reactant_terms = _parse_equation_side(left)
    product_terms = _parse_equation_side(right)

    if not reactant_terms or not product_terms:
        return BalancedEquation({}, {}, False, "empty side")

    # Collect all elements.
    all_elements: set[str] = set()
    for formula, _ in reactant_terms + product_terms:
        all_elements.update(_parse_formula_atoms(formula).keys())
    elements = sorted(all_elements)

    # Build the matrix: each row is an element, each column is a species.
    # Reactants are positive, products are negative.
    species = [f for f, _ in reactant_terms] + [f for f, _ in product_terms]
    n_reactants = len(reactant_terms)
    n_products = len(product_terms)

    rows = []
    for elem in elements:
        row = []
        for formula, _ in reactant_terms:
            atoms = _parse_formula_atoms(formula)
            row.append(atoms.get(elem, 0))
        for formula, _ in product_terms:
            atoms = _parse_formula_atoms(formula)
            row.append(-atoms.get(elem, 0))
        rows.append(row)

    matrix = Matrix(rows)
    nullspace = matrix.nullspace()
    if not nullspace:
        return BalancedEquation({}, {}, False, "no solution")

    # The nullspace vector gives the coefficients.
    vec = nullspace[0]
    # Convert to integers.
    denominators = [v.q for v in vec]
    common = lcm(denominators) if denominators else 1
    coeffs = [int(v * common) for v in vec]

    # Ensure all positive.
    if any(c < 0 for c in coeffs):
        coeffs = [-c for c in coeffs]

    reactant_coeffs = {species[i]: coeffs[i] for i in range(n_reactants)}
    product_coeffs = {species[n_reactants + i]: coeffs[n_reactants + i] for i in range(n_products)}

    return BalancedEquation(
        reactants=reactant_coeffs,
        products=product_coeffs,
        balanced=True,
    )


# ---------------------------------------------------------------------------
# Stoichiometry
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Molar mass
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Molecular descriptors (RDKit)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MolecularDescriptors:
    """RDKit-computed molecular descriptors for drug-likeness assessment."""

    smiles: str
    molecular_weight: float
    log_p: float  # partition coefficient (lipophilicity)
    tpsa: float  # topological polar surface area
    h_bond_donors: int  # Lipinski H-bond donors
    h_bond_acceptors: int  # Lipinski H-bond acceptors
    rotatable_bonds: int
    ring_count: int
    error: str | None = None


def compute_descriptors(smiles: str) -> MolecularDescriptors:
    """Compute molecular descriptors for a SMILES using RDKit.

    Returns MolecularDescriptors with error set on failure.
    """
    _ensure_rdkit()
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

    smiles = normalize_smiles_input(smiles.strip())
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return MolecularDescriptors(
                smiles=smiles,
                molecular_weight=0,
                log_p=0,
                tpsa=0,
                h_bond_donors=0,
                h_bond_acceptors=0,
                rotatable_bonds=0,
                ring_count=0,
                error="invalid SMILES",
            )
        canonical = Chem.MolToSmiles(mol)
        return MolecularDescriptors(
            smiles=canonical,
            molecular_weight=round(float(Descriptors.MolWt(mol)), 2),  # type: ignore[attr-defined]
            log_p=round(float(Crippen.MolLogP(mol)), 2),  # type: ignore[attr-defined]
            tpsa=round(float(Descriptors.TPSA(mol)), 2),  # type: ignore[attr-defined]
            h_bond_donors=int(Lipinski.NumHDonors(mol)),  # type: ignore[attr-defined]
            h_bond_acceptors=int(Lipinski.NumHAcceptors(mol)),  # type: ignore[attr-defined]
            rotatable_bonds=int(Lipinski.NumRotatableBonds(mol)),  # type: ignore[attr-defined]
            ring_count=int(rdMolDescriptors.CalcNumRings(mol)),
        )
    except Exception as exc:
        return MolecularDescriptors(
            smiles=smiles,
            molecular_weight=0,
            log_p=0,
            tpsa=0,
            h_bond_donors=0,
            h_bond_acceptors=0,
            rotatable_bonds=0,
            ring_count=0,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# pH / acid-base calculations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class pHResult:
    """Result of a pH / acid-base calculation."""

    answer: str
    ph: float | None = None
    poh: float | None = None
    error: str | None = None


def ph_from_concentration(h_concentration: float) -> pHResult:
    """Calculate pH from [H+] concentration (mol/L).

    pH = -log10([H+])
    """
    import math

    if h_concentration <= 0:
        return pHResult(answer="", error="concentration must be positive")
    ph = -math.log10(h_concentration)
    poh = 14.0 - ph
    return pHResult(
        answer=f"pH = -log10({h_concentration}) = {ph:.2f}",
        ph=round(ph, 2),
        poh=round(poh, 2),
    )


def ph_from_poh(poh: float) -> pHResult:
    """Calculate pH from pOH: pH = 14 - pOH."""
    ph = 14.0 - poh
    return pHResult(
        answer=f"pH = 14 - {poh} = {ph:.2f}",
        ph=round(ph, 2),
        poh=round(poh, 2),
    )


def h_from_ph(ph: float) -> pHResult:
    """Calculate [H+] from pH: [H+] = 10^(-pH)."""

    h_conc = 10 ** (-ph)
    return pHResult(
        answer=f"[H+] = 10^(-{ph}) = {h_conc:.2e} mol/L",
        ph=round(ph, 2),
    )


# ---------------------------------------------------------------------------
# Gas law calculations (ideal gas law)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GasLawResult:
    """Result of a gas law calculation."""

    answer: str
    value: float | None = None
    error: str | None = None


def ideal_gas_law(
    pressure: float | None = None,
    volume: float | None = None,
    moles: float | None = None,
    temperature: float | None = None,
) -> GasLawResult:
    """Solve PV=nRT for the missing variable.

    Exactly one of P, V, n, T must be None (the unknown).
    Temperature in Kelvin, pressure in atm, volume in L.
    R = 0.0821 L·atm/(mol·K).
    """
    R = 0.0821
    given = {"P": pressure, "V": volume, "n": moles, "T": temperature}
    none_count = sum(1 for v in given.values() if v is None)
    if none_count != 1:
        return GasLawResult(answer="", error="exactly one variable must be unknown (None)")

    if pressure is None:
        # P = nRT / V
        if volume is None or moles is None or temperature is None:
            return GasLawResult(answer="", error="missing required values")
        p = (moles * R * temperature) / volume
        return GasLawResult(
            answer=f"P = nRT/V = ({moles} * {R} * {temperature}) / {volume} = {p:.4f} atm",
            value=round(p, 4),
        )
    if volume is None:
        # V = nRT / P
        if pressure is None or moles is None or temperature is None:
            return GasLawResult(answer="", error="missing required values")
        v = (moles * R * temperature) / pressure
        return GasLawResult(
            answer=f"V = nRT/P = ({moles} * {R} * {temperature}) / {pressure} = {v:.4f} L",
            value=round(v, 4),
        )
    if moles is None:
        # n = PV / RT
        if pressure is None or volume is None or temperature is None:
            return GasLawResult(answer="", error="missing required values")
        n = (pressure * volume) / (R * temperature)
        return GasLawResult(
            answer=f"n = PV/RT = ({pressure} * {volume}) / ({R} * {temperature}) = {n:.4f} mol",
            value=round(n, 4),
        )
    # temperature is None → T = PV / nR
    if pressure is None or volume is None or moles is None:
        return GasLawResult(answer="", error="missing required values")
    t = (pressure * volume) / (moles * R)
    return GasLawResult(
        answer=f"T = PV/nR = ({pressure} * {volume}) / ({moles} * {R}) = {t:.4f} K",
        value=round(t, 4),
    )


# ---------------------------------------------------------------------------
# Solution chemistry (molarity, dilution)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SolutionResult:
    """Result of a solution chemistry calculation."""

    answer: str
    value: float | None = None
    error: str | None = None


def molarity(moles: float, volume_liters: float) -> SolutionResult:
    """Calculate molarity: M = moles / volume (L)."""
    if volume_liters <= 0:
        return SolutionResult(answer="", error="volume must be positive")
    m = moles / volume_liters
    return SolutionResult(
        answer=f"M = {moles} / {volume_liters} = {m:.4f} mol/L",
        value=round(m, 4),
    )


def dilution(
    m1: float,
    v1: float,
    v2: float | None = None,
    m2: float | None = None,
) -> SolutionResult:
    """Solve M1V1 = M2V2 for the missing variable.

    Exactly one of V2 or M2 must be None.
    """
    if v2 is None and m2 is None:
        return SolutionResult(answer="", error="one of V2 or M2 must be unknown")
    if v2 is not None and m2 is not None:
        return SolutionResult(answer="", error="only one of V2 or M2 can be unknown")
    if v2 is None:
        # V2 = M1V1 / M2
        if m2 is None or m2 == 0:
            return SolutionResult(answer="", error="M2 must be non-zero")
        v = (m1 * v1) / m2
        return SolutionResult(
            answer=f"V2 = M1V1/M2 = ({m1} * {v1}) / {m2} = {v:.4f} L",
            value=round(v, 4),
        )
    # m2 is None → M2 = M1V1 / V2
    if v2 == 0:
        return SolutionResult(answer="", error="V2 must be non-zero")
    m = (m1 * v1) / v2
    return SolutionResult(
        answer=f"M2 = M1V1/V2 = ({m1} * {v1}) / {v2} = {m:.4f} mol/L",
        value=round(m, 4),
    )


# ---------------------------------------------------------------------------
# Periodic table data
# ---------------------------------------------------------------------------

# Atomic masses (g/mol) and electronegativity (Pauling scale) for common elements.
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


# ---------------------------------------------------------------------------
# Limiting reagent
# ---------------------------------------------------------------------------


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
