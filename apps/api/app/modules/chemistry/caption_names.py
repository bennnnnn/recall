"""A molecule's caption keeps a name only when the app's own data gives that name its structure.

A model labelled ethanol's SMILES "Caffeine" and the phone drew it as caffeine (audit CHEM-04,
2026-11-13). A drawn molecule's caption is its formula and molar mass, from RDKit; the name the
model wrote stays in front of them only when it names the same structure: by the chemistry
tables (``species_facts.NAMED_COMPOUNDS`` and the formulas ``smiles`` maps), or else by the
PubChem lookup the chemistry context already uses, with its cache and its 2 s cap. A timeout,
a miss or another structure, and the caption is the formula and mass alone. Structures are
compared as RDKit's canonical SMILES without stereo marks.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping

from app.core.config import Settings

logger = logging.getLogger(__name__)

# The names one reply's drawings are looked up by, at most.
_MAX_LOOKUPS = 3
# A caption's name: no longer than a compound's name reasonably is.
_MAX_NAME_CHARS = 60


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


def same_structure(first: str, second: str) -> bool:
    """Two SMILES of one structure (RDKit's canonical form, stereo aside). In the pool."""
    from rdkit import Chem

    from app.modules.chemistry.smiles import parse_mol

    molecules = [parse_mol(first), parse_mol(second)]
    if any(molecule is None for molecule in molecules):
        return False
    left, right = (Chem.MolToSmiles(molecule, isomericSmiles=False) for molecule in molecules)
    return bool(left == right)


def checked_name(written: str, smiles: str, named: Mapping[str, str] | None) -> str | None:
    """The written caption's name when it names ``smiles``'s own structure, else None."""
    name = caption_name(written)
    if name is None:
        return None
    looked_up = table_smiles(name) or (named or {}).get(name_key(name))
    return name if looked_up and same_structure(looked_up, smiles) else None


async def checked_names(text: str, settings: Settings) -> dict[str, str]:
    """The names a reply's structures are labelled with that the tables do not give, by key,
    with the structure PubChem gives each, looked up within the chemistry context's budget.
    ``checked_name`` reads the tables' names itself."""
    from app.core.sympy_executor import run_sympy
    from app.modules.chemistry.fence import written_names

    if not settings.chemistry_enabled:
        return {}
    try:
        written = await run_sympy(written_names, text, timeout=settings.stem_solve_timeout_seconds)
    except Exception as exc:
        logger.info("structure captions not read: %s", type(exc).__name__)
        return {}
    names = {name_key(name): name for name in written if table_smiles(name) is None}
    keys = list(names)[:_MAX_LOOKUPS]
    found = await asyncio.gather(*(_pubchem_smiles(names[key]) for key in keys))
    return {key: smiles for key, smiles in zip(keys, found, strict=True) if smiles}


async def _pubchem_smiles(name: str) -> str | None:
    from app.core.redis import get_redis_client
    from app.gateways import pubchem_gateway
    from app.modules.chemistry.context import PUBCHEM_BUDGET_SECONDS

    try:
        lookup = await asyncio.wait_for(
            pubchem_gateway.lookup_by_name(name, redis=get_redis_client()),
            PUBCHEM_BUDGET_SECONDS,
        )
    except Exception as exc:
        # A timeout or an outage leaves the caption its formula and mass.
        logger.info("caption name not looked up: %s", type(exc).__name__)
        return None
    compound = lookup.compound
    return compound.smiles if compound is not None and lookup.error is None else None
