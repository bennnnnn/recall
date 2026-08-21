"""SMILES validation, molecular properties, and coordinates."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
_rdkit_loaded = False

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


def _ensure_rdkit() -> None:
    global _rdkit_loaded
    if _rdkit_loaded:
        return
    # Importing RDKit modules triggers the load.
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors

    _ = Chem, AllChem, Descriptors  # keep refs for mypy
    _rdkit_loaded = True


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
