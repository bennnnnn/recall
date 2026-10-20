"""Test helper: one push cycle on a single session.

The scheduler (``background/push_scheduler.py``) runs collect → dispatch → finalize with its own
sessions and lock; this runs the same push-service steps on the test's session. Steps are read
from the module at call time, so ``patch.object(push_service, ...)`` reaches them.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.notifications import push as push_service

logger = logging.getLogger(push_service.__name__)


async def run_push_cycle(session: AsyncSession, redis: Redis, settings: Settings) -> int:
    outbound = await push_service.collect_push_outbound(session, redis, settings)
    if not outbound:
        return 0
    delivered, invalid_tokens, receipt_tickets = await push_service.dispatch_expo(
        outbound, settings
    )
    for token in invalid_tokens:
        try:
            await push_service.push_repo.delete_by_token(session, token)
            logger.info("Pruned invalid push token=%s", token[:20])
        except Exception:
            logger.debug("Failed to prune push token", exc_info=True)
    if receipt_tickets:
        await push_service.enqueue_push_receipts(redis, receipt_tickets)
    await push_service.finalize_push_deliveries(session, outbound, delivered)
    return len(outbound)
