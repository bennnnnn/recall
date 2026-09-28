"""Deterministic organic checks that RDKit can decide without a reaction engine.

Functional groups use SMARTS. Stereochemistry uses RDKit CIP. Isomer class
compares formula and canonical SMILES. IUPAC names are not invented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# More specific groups come first so a carboxylic acid is not also a ketone.
_GROUPS: tuple[tuple[str, str], ...] = (
    ("carboxylic acid", "[CX3](=O)[OX2H1]"),
    ("ester", "[#6][CX3](=O)[OX2H0][#6]"),
    ("amide", "[NX3][CX3](=O)"),
    ("aldehyde", "[CX3H1](=O)"),
    ("ketone", "[#6][CX3](=O)[#6]"),
    ("phenol", "[OX2H][c]"),
    ("alcohol", "[OX2H][CX4]"),
    ("amine", "[NX3;H2,H1;!$(NC=O)]"),
    ("nitrile", "[CX2]#[NX1]"),
    ("alkyne", "[CX2]#[CX2]"),
    ("alkene", "[CX3;!a]=[CX3;!a]"),
    ("ether", "[OD2]([#6])[#6]"),
    ("haloalkane", "[CX4][F,Cl,Br,I]"),
    ("aromatic", "a"),
)
_SKIP_WHEN = {
    "ketone": {"carboxylic acid", "ester", "amide", "aldehyde"},
    "alcohol": {"carboxylic acid", "phenol"},
    "alkene": {"aromatic"},
    "amine": {"amide"},
}


@dataclass(frozen=True)
class OrganicFacts:
    """Verified structure facts. Mechanisms stay outside this result."""

    groups: tuple[str, ...]
    chirality: tuple[str, ...]
    double_bond_stereo: tuple[str, ...]
    formula: str
    canonical_smiles: str


def _mol(smiles: str) -> Any:
    from rdkit import Chem

    molecule = Chem.MolFromSmiles(smiles.strip())
    if molecule is None:
        return None
    return molecule


def organic_facts(smiles: str) -> OrganicFacts | None:
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    molecule = _mol(smiles)
    if molecule is None:
        return None
    found: list[str] = []
    for name, smarts in _GROUPS:
        if _SKIP_WHEN.get(name, set()) & set(found):
            continue
        query = Chem.MolFromSmarts(smarts)
        if query is not None and molecule.HasSubstructMatch(query):
            found.append(name)
    centers = Chem.FindMolChiralCenters(molecule, includeUnassigned=True)
    chirality = tuple(
        f"{molecule.GetAtomWithIdx(index).GetSymbol()}{index}={label}" for index, label in centers
    )
    stereo: list[str] = []
    for bond in molecule.GetBonds():
        code = str(bond.GetStereo())
        if code.endswith("STEREOZ"):
            stereo.append(f"bond {bond.GetIdx()} Z")
        elif code.endswith("STEREOE"):
            stereo.append(f"bond {bond.GetIdx()} E")
    return OrganicFacts(
        groups=tuple(found),
        chirality=chirality,
        double_bond_stereo=tuple(stereo),
        formula=rdMolDescriptors.CalcMolFormula(molecule),
        canonical_smiles=Chem.MolToSmiles(molecule),
    )


def isomer_relationship(left: str, right: str) -> str | None:
    """Identical, stereoisomers, constitutional isomers, or different compounds."""
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    first = _mol(left)
    second = _mol(right)
    if first is None or second is None:
        return None
    if rdMolDescriptors.CalcMolFormula(first) != rdMolDescriptors.CalcMolFormula(second):
        return "different compounds"
    iso_left = Chem.MolToSmiles(first)
    iso_right = Chem.MolToSmiles(second)
    if iso_left == iso_right:
        return "identical"
    plain_left = Chem.MolToSmiles(first, isomericSmiles=False)
    plain_right = Chem.MolToSmiles(second, isomericSmiles=False)
    if plain_left == plain_right:
        return "stereoisomers"
    return "constitutional isomers"
