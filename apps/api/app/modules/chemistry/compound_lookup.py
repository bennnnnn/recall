"""A compound looked up by name on PubChem, within the chemistry context's budget.

The chemistry context, a teaching figure and a caption's name check each looked a name up
with their own copy of the same call, timeout and checks. One lookup now: its cache is the
gateway's, its budget ``PUBCHEM_BUDGET_SECONDS``, and a miss, a timeout or an outage gives
no compound, which each caller answers in its own way. The name is never logged: it is the
user's words (SECURITY.md).
"""

from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis

from app.gateways import pubchem_gateway
from app.gateways.pubchem_gateway import PubChemCompound

logger = logging.getLogger(__name__)

# How long a turn waits on one PubChem lookup. PubChem is context, not a dependency: a slow
# lookup must not delay the first token.
PUBCHEM_BUDGET_SECONDS = 2.0


async def compound_by_name(name: str, *, redis: Redis | None) -> PubChemCompound | None:
    """The compound PubChem gives ``name``; None when it gives none in time."""
    try:
        lookup = await asyncio.wait_for(
            pubchem_gateway.lookup_by_name(name, redis=redis), PUBCHEM_BUDGET_SECONDS
        )
    except Exception as exc:  # A timeout or an outage finds nothing.
        logger.info("PubChem lookup gave up: %s name_chars=%d", type(exc).__name__, len(name))
        return None
    if lookup.error is not None or lookup.compound is None:
        logger.info("PubChem lookup found nothing name_chars=%d", len(name))
        return None
    return lookup.compound


async def structure_by_name(name: str) -> str | None:
    """The structure PubChem gives ``name``, with its stereo marks when PubChem gives them
    (a stereo name is held to them); None when it gives none."""
    from app.core.redis import get_redis_client

    compound = await compound_by_name(name, redis=get_redis_client())
    if compound is None:
        return None
    return compound.isomeric_smiles or compound.smiles
