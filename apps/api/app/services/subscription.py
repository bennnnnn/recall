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


def _plan_from_revenuecat_payload(payload: dict, settings: Settings) -> str:
    active = revenuecat_gateway.entitlement_active(
        payload,
        settings.revenuecat_entitlement_id,
    )
    return "pro" if active else "free"


async def sync_user_plan_from_revenuecat(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> User:
    if not settings.revenuecat_secret_key.strip():
        return user
    payload = await revenuecat_gateway.fetch_subscriber(
        settings.revenuecat_secret_key,
        str(user.id),
    )
    if payload is None:
        return user
    plan = _plan_from_revenuecat_payload(payload, settings)
    if plan == user.plan:
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
        return True
    await users_repo.update(session, user, plan=plan)
    logger.info("RevenueCat webhook set plan=%s user=%s", plan, user_id)
    return True
