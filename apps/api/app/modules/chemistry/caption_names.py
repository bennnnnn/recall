"""A molecule's caption keeps a name only when the app's own data gives that name its structure.

A model labelled ethanol's SMILES "Caffeine" and the phone drew it as caffeine (audit CHEM-04,
2026-11-13). A drawn molecule's caption is its formula and molar mass, from RDKit; the name the
model wrote stays in front of them only when it names the same structure: by the chemistry
tables (``species_facts.NAMED_COMPOUNDS`` and the formulas ``smiles`` maps), or else by the
PubChem lookup the chemistry context already uses, with its cache and its 2 s cap. A timeout,
a miss or another structure, and the caption is the formula and mass alone. Structures are
compared as RDKit's canonical SMILES: with their stereo marks when the name gives a stereo
descriptor, so "cis-2-butene" over trans ``C/C=C/C`` and "(R)-alanine" over (S) are other
structures (review, 2026-11-13); by their connections alone when it gives none, so
"Alanine" names either alanine. PubChem gives the structure with its stereo marks. The
PubChem look-up, before the pool draws the molecules, is ``caption_lookup``; a caption
nothing checked goes (``structure_captions``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping

# A caption's name: no longer than a compound's name reasonably is.
_MAX_NAME_CHARS = 60
# A name's stereo descriptor (IUPAC): cis-, trans-, meso-, L-, D-, (R)-, (2R,3S)-, (E)-, (Z)-,
# (+)-, (-)-, (±)-.
_STEREO_DESCRIPTOR = re.compile(
    r"(?:^|[\s(\[,-])(?:(?i:cis|trans|meso)|[DL])-"
    r"|\((?:\d*[RSEZ](?:\s*,\s*\d*[RSEZ])*|[+\u2212\u00b1-])\)"
)


def caption_name(written: str) -> str | None:
    """The name a model's caption starts with ("Caffeine", from "**Caffeine** · C8H10N4O2"),
    or None when its first line is no name."""
    first = written.strip().split("\n", 1)[0].split(" · ", 1)[0]
    name = first.strip(" \t*_`:")
    if not name or len(name) > _MAX_NAME_CHARS or not any(char.isalpha() for char in name):
        return None
    return name


def name_key(name: str) -> str:
    return " ".join(name.split()).casefold()


def table_smiles(name: str) -> str | None:
    """The structure the chemistry tables give a name, when they give one: water is ``O``;
    ethanol's table formula (C2H5OH) is no structure, so the tables give none."""
    from app.modules.chemistry.smiles import normalize_smiles_input
    from app.modules.chemistry.species_facts import NAMED_COMPOUNDS

    formula = NAMED_COMPOUNDS.get(name_key(name))
    if formula is None:
        return None
    mapped = normalize_smiles_input(formula)
    return mapped if mapped != formula else None


def names_stereo(name: str) -> bool:
    """Whether a name gives a stereo descriptor ("L-alanine", "cis-2-butene")."""
    return _STEREO_DESCRIPTOR.search(name) is not None


def same_structure(first: str, second: str, *, stereo: bool = True) -> bool:
    """Two SMILES of one structure (RDKit's canonical form), their stereo marks included or,
    ``stereo`` False, their connections alone. In the pool."""
    from rdkit import Chem

    from app.modules.chemistry.smiles import parse_mol

    molecules = [parse_mol(first), parse_mol(second)]
    if any(molecule is None for molecule in molecules):
        return False
    left, right = (Chem.MolToSmiles(molecule, isomericSmiles=stereo) for molecule in molecules)
    return bool(left == right)


def checked_name(written: str, smiles: str, named: Mapping[str, str] | None) -> str | None:
    """The written caption's name when it names ``smiles``'s own structure, else None."""
    name = caption_name(written)
    if name is None:
        return None
    looked_up = table_smiles(name) or (named or {}).get(name_key(name))
    stereo = names_stereo(name)
    return name if looked_up and same_structure(looked_up, smiles, stereo=stereo) else None
