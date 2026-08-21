"""RevenueCat webhook — keep backend plan in sync with store entitlements."""

from __future__ import annotations

import hmac
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.deps import get_redis
from app.core.jobs import enqueue_purchase_receipt
from app.core.redis_lock import acquire_lock
from app.services import revenuecat_webhook as webhook_service

subscription_service = webhook_service.subscription_service
_already_processed = webhook_service._already_processed
_try_claim = webhook_service._try_claim
_expiration = webhook_service._expiration

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Cap before body parse — endpoint is rate-limit-exempt and auth runs in-handler.
_MAX_WEBHOOK_BODY_BYTES = 64 * 1024


def _secrets_match(candidate: str, expected: str) -> bool:
    # hmac.compare_digest(str, str) raises TypeError on non-ASCII. Starlette
    # decodes headers as latin-1, so a 0x80-0xFF byte would 500 this
    # rate-limit-exempt route instead of 401.
    if not candidate.isascii() or not expected.isascii():
        return False
    return hmac.compare_digest(candidate, expected)


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
    authorized = any(_secrets_match(c, expected) for c in candidates)
    if not authorized:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


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

    try:
        await webhook_service.process_event(
            session,
            redis,
            settings,
            payload,
            processed_check=_already_processed,
            event_claim=_try_claim,
            subscriber_lock=acquire_lock,
            receipt_enqueuer=enqueue_purchase_receipt,
        )
    except webhook_service.SubscriberBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RevenueCat webhook busy for subscriber",
        ) from exc
