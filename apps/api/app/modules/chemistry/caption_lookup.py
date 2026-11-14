"""The PubChem half of a caption name's check, before the pool draws the molecules.

``caption_names`` reads a name and holds it to its structure; a name the chemistry tables do
not give is looked up here, on the PubChem lookup the chemistry context already uses (its
cache and its 2 s budget). A miss or a timeout gives no structure, so the caption keeps its
formula and mass alone.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.aio import gather_or_cancel
from app.core.config import Settings
from app.modules.chemistry.caption_names import name_key, table_smiles

logger = logging.getLogger(__name__)

# The names one reply's drawings are looked up by, at most.
_MAX_LOOKUPS = 3


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
    found = await gather_or_cancel(*(_pubchem_smiles(names[key]) for key in keys))
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
    if compound is None or lookup.error is not None:
        return None
    # With its stereo marks when PubChem gives them: a stereo name is held to them.
    return compound.isomeric_smiles or compound.smiles
