"""RevenueCat webhook — keep backend plan in sync with store entitlements."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.services import subscription as subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_PRO_EVENTS = frozenset(
    {
        "INITIAL_PURCHASE",
        "RENEWAL",
        "UNCANCELLATION",
        "NON_RENEWING_PURCHASE",
        "PRODUCT_CHANGE",
        "SUBSCRIPTION_EXTENDED",
    }
)
_FREE_EVENTS = frozenset({"CANCELLATION", "EXPIRATION", "BILLING_ISSUE"})


def _verify_auth(authorization: str | None, settings: Settings) -> None:
    expected = settings.revenuecat_webhook_auth.strip()
    if not expected:
        if settings.environment == "development":
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RevenueCat webhook not configured",
        )
    token = (authorization or "").strip()
    if token != expected and token != f"Bearer {expected}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def _app_user_id(payload: dict[str, Any]) -> str | None:
    event = payload.get("event")
    if not isinstance(event, dict):
        return None
    for key in ("app_user_id", "original_app_user_id"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _event_type(payload: dict[str, Any]) -> str:
    event = payload.get("event")
    if isinstance(event, dict):
        et = event.get("type")
        if isinstance(et, str):
            return et
    return ""


@router.post("/revenuecat", status_code=status.HTTP_204_NO_CONTENT)
async def revenuecat_webhook(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    _verify_auth(authorization, settings)
    app_user_id = _app_user_id(payload)
    if not app_user_id:
        return

    event_type = _event_type(payload)
    if event_type in _PRO_EVENTS:
        await subscription_service.apply_plan_for_app_user_id(
            session,
            app_user_id,
            plan="pro",
        )
        return
    if event_type in _FREE_EVENTS:
        await subscription_service.apply_plan_for_app_user_id(
            session,
            app_user_id,
            plan="free",
        )
