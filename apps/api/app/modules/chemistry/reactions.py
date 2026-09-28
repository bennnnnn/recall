"""One-product school reactions. A curved-arrow mechanism is not a result."""

from __future__ import annotations

from typing import Any

_HALOGENS = frozenset({"F", "Cl", "Br", "I"})


def named_product(reaction: str, smiles: str, partner: str | None = None) -> str | None:
    """Return one canonical product SMILES, or None when the match is not unique."""
    molecule = _mol(smiles)
    if molecule is None:
        return None
    if reaction == "bromine":
        return _add_across_alkene(molecule, "Br", "Br")
    if reaction == "hbr":
        return _add_across_alkene(molecule, "Br", None)
    if reaction == "hydration":
        return _add_across_alkene(molecule, "O", None)
    if reaction == "hydroxide":
        return _substitute_primary_halide(molecule)
    if reaction == "esterification":
        return _ester(molecule, partner)
    return None


def _mol(smiles: str) -> Any:
    from rdkit import Chem

    return Chem.MolFromSmiles(smiles.strip())


def _alkene_bond(molecule: Any) -> tuple[int, int] | None:
    from rdkit import Chem

    found: list[tuple[int, int]] = []
    for bond in molecule.GetBonds():
        if bond.GetBondType() != Chem.BondType.DOUBLE:
            continue
        left = bond.GetBeginAtom()
        right = bond.GetEndAtom()
        if left.GetSymbol() != "C" or right.GetSymbol() != "C":
            continue
        if left.GetIsAromatic() or right.GetIsAromatic():
            continue
        found.append((left.GetIdx(), right.GetIdx()))
    if len(found) != 1:
        return None
    return found[0]


def _carbon_neighbors(molecule: Any, index: int, other: int) -> int:
    atom = molecule.GetAtomWithIdx(index)
    return sum(
        1
        for neighbor in atom.GetNeighbors()
        if neighbor.GetIdx() != other and neighbor.GetSymbol() == "C"
    )


def _add_across_alkene(molecule: Any, first: str, second: str | None) -> str | None:
    from rdkit import Chem

    bond = _alkene_bond(molecule)
    if bond is None:
        return None
    left, right = bond
    left_subs = _carbon_neighbors(molecule, left, right)
    right_subs = _carbon_neighbors(molecule, right, left)
    rich = left if left_subs >= right_subs else right
    poor = right if rich == left else left
    edited = Chem.RWMol(molecule)
    edited.GetBondBetweenAtoms(left, right).SetBondType(Chem.BondType.SINGLE)
    _attach(edited, rich, first)
    if second is not None:
        _attach(edited, poor, second)
    return _canonical(edited)


def _attach(molecule: Any, index: int, symbol: str) -> None:
    from rdkit import Chem

    added = molecule.AddAtom(Chem.Atom(symbol))
    molecule.AddBond(index, added, Chem.BondType.SINGLE)


def _substitute_primary_halide(molecule: Any) -> str | None:
    from rdkit import Chem

    sites: list[int] = []
    for atom in molecule.GetAtoms():
        if atom.GetSymbol() != "C":
            continue
        carbons = [neighbor for neighbor in atom.GetNeighbors() if neighbor.GetSymbol() == "C"]
        halogens = [
            neighbor for neighbor in atom.GetNeighbors() if neighbor.GetSymbol() in _HALOGENS
        ]
        if len(carbons) == 1 and len(halogens) == 1:
            sites.append(halogens[0].GetIdx())
    if len(sites) != 1:
        return None
    edited = Chem.RWMol(molecule)
    edited.GetAtomWithIdx(sites[0]).SetAtomicNum(8)
    return _canonical(edited)


def _ester(acid: Any, partner: str | None) -> str | None:
    from rdkit.Chem import AllChem

    if not partner:
        return None
    alcohol = _mol(partner)
    if alcohol is None:
        return None
    reaction = AllChem.ReactionFromSmarts(  # type: ignore[attr-defined]
        "[C:1](=[O:2])[OH].[OH][C:3]>>[C:1](=[O:2])O[C:3]"
    )
    found: set[str] = set()
    for outcome in reaction.RunReactants((acid, alcohol)):
        smiles = _canonical(outcome[0])
        if smiles is not None:
            found.add(smiles)
    if len(found) != 1:
        return None
    return next(iter(found))


def _canonical(molecule: Any) -> str | None:
    from rdkit import Chem

    try:
        Chem.SanitizeMol(molecule)
    except (ValueError, RuntimeError):
        return None
    return Chem.MolToSmiles(molecule)
