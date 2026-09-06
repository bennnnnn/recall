"""Periodic RevenueCat entitlement check for users currently marked Pro.

A lost webhook (or exhausted retry after a non-200) can leave plan=pro after
the store has already revoked access. App-open sync only helps if they reopen
the app. This cycle re-verifies Pro rows against RevenueCat's REST API.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.background.periodic import (
    CycleLock,
    lock_ttl_yield_next_tick,
    run_locked_cycle,
    start_periodic,
    stop_periodic,
)
from app.core.config import Settings
from app.core.db import SessionLocal
from app.repositories import users as users_repo
from app.services import subscription as subscription_service

logger = logging.getLogger(__name__)

_NAME = "billing_reconcile"
LOCK_KEY = "recall:billing_reconcile:lock"
_REST_GAP_SECONDS = 0.2


def _scheduler_enabled(settings: Settings) -> bool:
    return settings.billing_reconcile_enabled and bool(settings.revenuecat_secret_key.strip())


async def _billing_cycle(settings: Settings, lock: CycleLock) -> None:
    if not settings.revenuecat_secret_key.strip():
        return
    after_id: UUID | None = None
    batch = max(1, settings.billing_reconcile_batch_size)
    while True:
        async with SessionLocal() as session:
            ids = await users_repo.list_ids_by_plan(
                session, plan="pro", after_id=after_id, limit=batch
            )
        if not ids:
            return
        for user_id in ids:
            plan = await subscription_service.resolve_plan_from_revenuecat(settings, str(user_id))
            if plan is not None and plan != "pro":
                async with SessionLocal() as session:
                    await subscription_service.apply_plan_for_app_user_id(
                        session, str(user_id), plan=plan
                    )
                    logger.info("Billing reconcile set plan=%s user=%s", plan, user_id)
            if not await lock.refresh():
                logger.warning("Billing reconcile lock lost; stopping cycle")
                return
            await asyncio.sleep(_REST_GAP_SECONDS)
        after_id = ids[-1]


async def run_billing_reconcile_cycle(settings: Settings) -> None:
    await run_locked_cycle(
        name="billing reconcile",
        lock_key=LOCK_KEY,
        lock_ttl_seconds=lock_ttl_yield_next_tick(settings.billing_reconcile_interval_seconds),
        enabled=_scheduler_enabled(settings),
        fn=_billing_cycle,
        settings=settings,
    )


async def start_billing_reconcile_scheduler(settings: Settings) -> None:
    await start_periodic(
        name=_NAME,
        interval_seconds=max(1, settings.billing_reconcile_interval_seconds),
        enabled=_scheduler_enabled(settings),
        cycle=run_billing_reconcile_cycle,
        settings=settings,
    )


async def stop_billing_reconcile_scheduler() -> None:
    await stop_periodic(_NAME)
