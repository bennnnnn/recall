"""RevenueCat webhook — keep backend plan in sync with store entitlements."""

from __future__ import annotations

import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.deps import get_redis
from app.core.jobs import enqueue_purchase_receipt
from app.services import subscription as subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Cap before body parse — endpoint is rate-limit-exempt and auth runs in-handler.
_MAX_WEBHOOK_BODY_BYTES = 64 * 1024

# RevenueCat retries webhooks; dedup event ids for ~24h so a replay doesn't
# reprocess (and, via the receipt path, re-email) the same event.
_EVENT_ID_TTL = 60 * 60 * 24
# Short lock while a delivery is in flight — two concurrent deliveries of the
# same event_id must not both pass a check-then-act exists() race.
_EVENT_CLAIM_TTL = 120

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
# BILLING_ISSUE is intentionally omitted: payment failed but the subscriber may
# still be in a grace/retry window. Downgrade only on EXPIRATION (or cancel).
_FREE_EVENTS = frozenset({"CANCELLATION", "EXPIRATION"})


def _done_key(event_id: str) -> str:
    return f"rcwebhook:{event_id}"


def _lock_key(event_id: str) -> str:
    return f"rcwebhook:lock:{event_id}"


async def _already_processed(redis: Redis, event_id: str) -> bool:
    return bool(await redis.exists(_done_key(event_id)))


async def _try_claim(redis: Redis, event_id: str) -> bool:
    """Atomically claim this event for in-flight processing."""
    return bool(await redis.set(_lock_key(event_id), "1", nx=True, ex=_EVENT_CLAIM_TTL))


async def _mark_processed(redis: Redis, event_id: str) -> None:
    await redis.set(_done_key(event_id), "1", ex=_EVENT_ID_TTL)


async def _release_claim(redis: Redis, event_id: str) -> None:
    await redis.delete(_lock_key(event_id))


def _verify_auth(authorization: str | None, settings: Settings) -> None:
    expected = settings.revenuecat_webhook_auth.strip()
    if not expected:
        # Never skip auth based on `environment` alone — a dev config on a
        # public host would let anyone grant themselves Pro. Require an
        # explicit opt-in (DEV_ALLOW_UNAUTHED_WEBHOOKS) for local testing.
        if settings.dev_allow_unauthed_webhooks:
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


def _event_environment(payload: dict[str, Any]) -> str | None:
    """RevenueCat sends ``event.environment`` as PRODUCTION or SANDBOX."""
    event = payload.get("event")
    if isinstance(event, dict):
        value = event.get("environment")
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def _ignore_sandbox_event(payload: dict[str, Any], settings: Settings) -> bool:
    """Sandbox purchases must not grant Pro on a production API host.

    Local/dev still processes SANDBOX so storekit testing can exercise the
    webhook path. Production (and any non-development environment) ACK with
    204 and skip plan mutation.
    """
    if _event_environment(payload) != "SANDBOX":
        return False
    return settings.environment.strip().lower() != "development"


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
        return datetime.fromtimestamp(secs, tz=UTC).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        # Huge / negative ms must not 500 the webhook (RevenueCat retry storm).
        return None


async def _dispatch_event(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    payload: dict[str, Any],
    event_type: str,
    app_user_id: str,
) -> bool:
    """Process the event. Returns True if it mutated plan state (and should
    therefore be deduped against future retries); False for event types we
    intentionally ignore, which are safe to reprocess if replayed."""
    if event_type == "TRANSFER":
        event = payload.get("event")
        if isinstance(event, dict):
            new_id = event.get("app_user_id")
            old_ids = event.get("transferred_from") or []
            if isinstance(new_id, str) and new_id.strip():
                from_list = old_ids if isinstance(old_ids, list) else []
                await subscription_service.handle_revenuecat_transfer(
                    session,
                    settings,
                    new_app_user_id=new_id,
                    transferred_from=[oid for oid in from_list if isinstance(oid, str)],
                )
        return True
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
        return True
    if event_type in _FREE_EVENTS:
        await subscription_service.apply_plan_for_app_user_id(
            session,
            app_user_id,
            plan="free",
        )
        return True
    return False


def _reject_oversized_webhook_body(content_length: str | None, body_len: int) -> None:
    if content_length is not None:
        try:
            if int(content_length) > _MAX_WEBHOOK_BODY_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Webhook payload too large",
                )
        except ValueError:
            pass
    if body_len > _MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Webhook payload too large",
        )


@router.post("/revenuecat", status_code=status.HTTP_204_NO_CONTENT)
async def revenuecat_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
) -> None:
    # Auth + size before JSON parse — unauthenticated body work is a DoS vector
    # (this path is exempt from the global REST rate limiter).
    _verify_auth(request.headers.get("Authorization"), settings)
    _reject_oversized_webhook_body(request.headers.get("content-length"), 0)
    body = await request.body()
    _reject_oversized_webhook_body(None, len(body))
    try:
        parsed: Any = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON",
        )
    payload: dict[str, Any] = parsed

    if _ignore_sandbox_event(payload, settings):
        logger.info(
            "RevenueCat sandbox webhook ignored in %s environment",
            settings.environment,
        )
        return

    # Dedup: done-marker (24h) + short NX lock so concurrent deliveries of the
    # same event_id cannot both process (duplicate receipt emails). Mark only
    # after success so a mid-processing failure still allows RevenueCat retry.
    event_id = _event_id(payload)
    claimed = False
    if event_id:
        if await _already_processed(redis, event_id):
            logger.info("RevenueCat webhook replay ignored event_id=%s", event_id)
            return
        claimed = await _try_claim(redis, event_id)
        if not claimed:
            logger.info("RevenueCat webhook in-flight ignored event_id=%s", event_id)
            return

    app_user_id = _app_user_id(payload)
    if not app_user_id:
        if claimed and event_id:
            await _release_claim(redis, event_id)
        return

    event_type = _event_type(payload)
    try:
        processed = await _dispatch_event(
            session, redis, settings, payload, event_type, app_user_id
        )
        if processed and event_id:
            await _mark_processed(redis, event_id)
    finally:
        if claimed and event_id:
            await _release_claim(redis, event_id)
