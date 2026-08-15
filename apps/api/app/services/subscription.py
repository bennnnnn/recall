"""Sync user plan from RevenueCat entitlements."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import revenuecat_gateway
from app.models.orm import User
from app.repositories import users as users_repo

logger = logging.getLogger(__name__)


async def is_stale_rc_event(
    session: AsyncSession,
    app_user_id: str,
    event_timestamp_ms: int,
) -> bool:
    """True when *event_timestamp_ms* is older than the user's last RC event."""
    try:
        user_id = UUID(app_user_id)
    except ValueError:
        return False
    user = await users_repo.get_by_id(session, user_id)
    if user is None or user.rc_last_event_at_ms is None:
        return False
    return event_timestamp_ms < user.rc_last_event_at_ms


async def advance_rc_event_watermark(
    session: AsyncSession,
    app_user_id: str,
    event_timestamp_ms: int,
) -> None:
    """Move the per-user RC event watermark forward (never backward)."""
    try:
        user_id = UUID(app_user_id)
    except ValueError:
        return
    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        return
    if user.rc_last_event_at_ms is not None and event_timestamp_ms <= user.rc_last_event_at_ms:
        return
    await users_repo.update(session, user, rc_last_event_at_ms=event_timestamp_ms)


def _plan_from_revenuecat_payload(payload: dict, settings: Settings) -> str:
    active = revenuecat_gateway.entitlement_active(
        payload,
        settings.revenuecat_entitlement_id,
    )
    return "pro" if active else "free"


async def resolve_plan_from_revenuecat(settings: Settings, app_user_id: str) -> str | None:
    """HTTP-only: return ``pro``/``free`` from the subscriber API, or None if
    the secret is missing or the fetch failed. Never defaults to ``pro``."""
    if not settings.revenuecat_secret_key.strip():
        return None
    payload = await revenuecat_gateway.fetch_subscriber(
        settings.revenuecat_secret_key,
        app_user_id,
    )
    if payload is None:
        return None
    return _plan_from_revenuecat_payload(payload, settings)


async def sync_user_plan_from_revenuecat(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> User:
    plan = await resolve_plan_from_revenuecat(settings, str(user.id))
    if plan is None or plan == user.plan:
        return user
    updated = await users_repo.update(session, user, plan=plan)
    logger.info("Updated plan from RevenueCat user=%s plan=%s", user.id, plan)
    return updated


async def apply_plan_for_app_user_id(
    session: AsyncSession,
    app_user_id: str,
    *,
    plan: str,
) -> bool:
    try:
        user_id = UUID(app_user_id)
    except ValueError:
        logger.warning("RevenueCat webhook ignored invalid app_user_id=%s", app_user_id)
        return False
    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        logger.warning("RevenueCat webhook user not found id=%s", app_user_id)
        return False
    if user.plan == plan:
        # No change — return False so the caller doesn't fire a duplicate
        # receipt email on every RENEWAL/replay of an already-Pro user.
        return False
    await users_repo.update(session, user, plan=plan)
    logger.info("RevenueCat webhook set plan=%s user=%s", plan, user_id)
    return True


async def handle_revenuecat_transfer(
    session: AsyncSession,
    settings: Settings,
    *,
    new_app_user_id: str,
    transferred_from: list[str],
) -> bool:
    """Move entitlements between app user ids.

    Fetches the target's plan from the RevenueCat API *before* any writes, then
    upgrades the target and only then downgrades sources. Returns False when
    the target plan could not be resolved so the webhook is not deduped and
    RevenueCat can retry. Never defaults the target to ``pro``.
    """
    cleaned_new = new_app_user_id.strip()
    if not cleaned_new:
        return False
    try:
        user_id = UUID(cleaned_new)
    except ValueError:
        logger.warning("RevenueCat TRANSFER ignored invalid app_user_id=%s", cleaned_new)
        return False

    plan = await resolve_plan_from_revenuecat(settings, cleaned_new)
    if plan is None:
        logger.warning(
            "RevenueCat TRANSFER deferred; subscriber fetch failed app_user_id=%s",
            cleaned_new,
        )
        return False

    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        logger.warning("RevenueCat TRANSFER user not found id=%s", cleaned_new)
        return False
    if user.plan != plan:
        await users_repo.update(session, user, plan=plan)
        logger.info("RevenueCat TRANSFER set plan=%s user=%s", plan, user_id)

    for old_id in transferred_from:
        cleaned = old_id.strip()
        if cleaned:
            await apply_plan_for_app_user_id(session, cleaned, plan="free")
    return True
