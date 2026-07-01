"""RevenueCat webhook — keep backend plan in sync with store entitlements."""

from __future__ import annotations

import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.deps import get_redis
from app.core.jobs import enqueue_purchase_receipt
from app.services import subscription as subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# RevenueCat retries webhooks; dedup event ids for ~24h so a replay doesn't
# reprocess (and, via the receipt path, re-email) the same event.
_EVENT_ID_TTL = 60 * 60 * 24

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
    # Accept either the raw shared secret or a Bearer-prefixed form. Compare in
    # constant time to avoid leaking whether the prefix matched via timing.
    candidates = (
        [token, token.removeprefix("Bearer ").strip()] if token.startswith("Bearer ") else [token]
    )
    authorized = any(hmac.compare_digest(c, expected) for c in candidates)
    if not authorized:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def _event_id(payload: dict[str, Any]) -> str | None:
    event = payload.get("event")
    if not isinstance(event, dict):
        return None
    for key in ("event_id", "id"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def _already_seen(redis: Redis, event_id: str) -> bool:
    # SETNX returns 1 if the key was set (first sighting), 0 if it already
    # existed (replay). True here means "already seen".
    inserted = await redis.set(f"rcwebhook:{event_id}", "1", ex=_EVENT_ID_TTL, nx=True)
    return not inserted


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


def _event_field(payload: dict[str, Any], key: str) -> str | None:
    event = payload.get("event")
    if isinstance(event, dict):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _expiration(payload: dict[str, Any]) -> str | None:
    """RevenueCat sends `expiration_at_ms` (epoch ms) for subscriptions."""
    event = payload.get("event")
    if not isinstance(event, dict):
        return None
    raw = event.get("expiration_at_ms")
    if raw is None:
        return None
    try:
        secs = int(raw) / 1000.0
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(secs, tz=UTC).isoformat()


@router.post("/revenuecat", status_code=status.HTTP_204_NO_CONTENT)
async def revenuecat_webhook(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    _verify_auth(authorization, settings)
    # Dedup RevenueCat retries: if we've already processed this event id, stop.
    event_id = _event_id(payload)
    if event_id and await _already_seen(redis, event_id):
        logger.info("RevenueCat webhook replay ignored event_id=%s", event_id)
        return
    app_user_id = _app_user_id(payload)
    if not app_user_id:
        return

    event_type = _event_type(payload)
    if event_type in _PRO_EVENTS:
        applied = await subscription_service.apply_plan_for_app_user_id(
            session,
            app_user_id,
            plan="pro",
        )
        if applied and settings.email_enabled:
            await enqueue_purchase_receipt(
                redis,
                app_user_id,
                event_type=event_type,
                store=_event_field(payload, "store"),
                product_id=_event_field(payload, "product_id"),
                expiration=_expiration(payload),
            )
        return
    if event_type in _FREE_EVENTS:
        await subscription_service.apply_plan_for_app_user_id(
            session,
            app_user_id,
            plan="free",
        )
