"""RevenueCat webhook state transition orchestration."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.jobs import enqueue_purchase_receipt
from app.core.redis_lock import acquire_lock, release_lock
from app.services import subscription as subscription_service

logger = logging.getLogger(__name__)

_EVENT_ID_TTL = 60 * 60 * 24
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
_FREE_EVENTS = frozenset({"EXPIRATION"})
_ORDERED_EVENTS = _PRO_EVENTS | _FREE_EVENTS | frozenset({"CANCELLATION", "TRANSFER"})


class SubscriberBusyError(Exception):
    """Another RevenueCat event is updating the same subscriber."""


ReceiptEnqueuer = Callable[..., Awaitable[Any]]
ProcessedCheck = Callable[[Redis, str], Awaitable[bool]]
EventClaim = Callable[[Redis, str], Awaitable[bool]]
SubscriberLock = Callable[[Redis, str, int], Awaitable[str | None]]


def _event(payload: dict[str, Any]) -> dict[str, Any] | None:
    value = payload.get("event")
    return value if isinstance(value, dict) else None


def event_environment(payload: dict[str, Any]) -> str | None:
    event = _event(payload)
    value = event.get("environment") if event else None
    return value.strip().upper() if isinstance(value, str) and value.strip() else None


def should_ignore_sandbox(payload: dict[str, Any], settings: Settings) -> bool:
    return (
        event_environment(payload) == "SANDBOX"
        and settings.environment.strip().lower() != "development"
    )


def _string_field(payload: dict[str, Any], key: str) -> str | None:
    event = _event(payload)
    value = event.get(key) if event else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _event_id(payload: dict[str, Any]) -> str | None:
    explicit = _string_field(payload, "event_id") or _string_field(payload, "id")
    if explicit:
        return explicit
    event = _event(payload)
    if event is None:
        return None
    canonical = json.dumps(event, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _app_user_id(payload: dict[str, Any]) -> str | None:
    return _string_field(payload, "app_user_id") or _string_field(payload, "original_app_user_id")


def _event_type(payload: dict[str, Any]) -> str:
    return _string_field(payload, "type") or ""


def _int_field(payload: dict[str, Any], key: str) -> int | None:
    event = _event(payload)
    raw = event.get(key) if event else None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _expiration(payload: dict[str, Any]) -> str | None:
    milliseconds = _int_field(payload, "expiration_at_ms")
    if milliseconds is None:
        return None
    try:
        return datetime.fromtimestamp(milliseconds / 1000.0, tz=UTC).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _cancellation_should_downgrade(payload: dict[str, Any]) -> bool:
    milliseconds = _int_field(payload, "expiration_at_ms")
    if milliseconds is None:
        return True
    try:
        return datetime.fromtimestamp(milliseconds / 1000.0, tz=UTC) <= datetime.now(tz=UTC)
    except (OverflowError, OSError, ValueError):
        return True


def _done_key(event_id: str) -> str:
    return f"rcwebhook:{event_id}"


def _event_lock_key(event_id: str) -> str:
    return f"rcwebhook:lock:{event_id}"


def _subscriber_lock_key(app_user_id: str) -> str:
    return f"rcwebhook:user:{app_user_id}"


async def _already_processed(redis: Redis, event_id: str) -> bool:
    return bool(await redis.exists(_done_key(event_id)))


async def _try_claim(redis: Redis, event_id: str) -> bool:
    return bool(
        await redis.set(
            _event_lock_key(event_id),
            "1",
            nx=True,
            ex=_EVENT_CLAIM_TTL,
        )
    )


async def _dispatch_event(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    payload: dict[str, Any],
    event_type: str,
    app_user_id: str,
    receipt_enqueuer: ReceiptEnqueuer,
) -> bool:
    if event_type == "TRANSFER":
        event = _event(payload)
        if event is None:
            return False
        new_id = event.get("app_user_id")
        old_ids = event.get("transferred_from") or []
        if not isinstance(new_id, str) or not new_id.strip():
            return False
        from_list = old_ids if isinstance(old_ids, list) else []
        return await subscription_service.handle_revenuecat_transfer(
            session,
            settings,
            new_app_user_id=new_id,
            transferred_from=[old_id for old_id in from_list if isinstance(old_id, str)],
        )
    if event_type in _PRO_EVENTS:
        plan = await subscription_service.resolve_plan_from_revenuecat(settings, app_user_id)
        if plan is None:
            logger.warning(
                "RevenueCat %s deferred; subscriber fetch failed app_user_id=%s",
                event_type,
                app_user_id,
            )
            return False
        applied = await subscription_service.apply_plan_for_app_user_id(
            session, app_user_id, plan=plan
        )
        if applied and plan == "pro" and settings.email_enabled:
            await receipt_enqueuer(
                redis,
                app_user_id,
                event_type=event_type,
                store=_string_field(payload, "store"),
                product_id=_string_field(payload, "product_id"),
                expiration=_expiration(payload),
            )
        return True
    if event_type == "CANCELLATION":
        if not _cancellation_should_downgrade(payload):
            logger.info(
                "RevenueCat CANCELLATION ignored until period end app_user_id=%s",
                app_user_id,
            )
            return True
        await subscription_service.apply_plan_for_app_user_id(session, app_user_id, plan="free")
        return True
    if event_type in _FREE_EVENTS:
        await subscription_service.apply_plan_for_app_user_id(session, app_user_id, plan="free")
        return True
    return False


async def _advance_transfer_watermarks(
    session: AsyncSession,
    payload: dict[str, Any],
    event_timestamp_ms: int,
) -> None:
    event = _event(payload)
    old_ids = event.get("transferred_from") or [] if event else []
    if not isinstance(old_ids, list):
        return
    for old_id in old_ids:
        if isinstance(old_id, str) and old_id.strip():
            await subscription_service.advance_rc_event_watermark(
                session, old_id.strip(), event_timestamp_ms
            )


async def process_event(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    payload: dict[str, Any],
    *,
    processed_check: ProcessedCheck = _already_processed,
    event_claim: EventClaim = _try_claim,
    subscriber_lock: SubscriberLock = acquire_lock,
    receipt_enqueuer: ReceiptEnqueuer = enqueue_purchase_receipt,
) -> None:
    """Apply one authenticated, parsed RevenueCat delivery."""
    if should_ignore_sandbox(payload, settings):
        logger.info(
            "RevenueCat sandbox webhook ignored in %s environment",
            settings.environment,
        )
        return

    event_id = _event_id(payload)
    claimed = False
    if event_id:
        if await processed_check(redis, event_id):
            logger.info("RevenueCat webhook replay ignored event_id=%s", event_id)
            return
        claimed = await event_claim(redis, event_id)
        if not claimed:
            logger.info("RevenueCat webhook in-flight ignored event_id=%s", event_id)
            return

    app_user_id = _app_user_id(payload)
    if not app_user_id:
        if claimed and event_id:
            await redis.delete(_event_lock_key(event_id))
        return

    event_type = _event_type(payload)
    event_timestamp_ms = _int_field(payload, "event_timestamp_ms")
    subscriber_key = _subscriber_lock_key(app_user_id)
    subscriber_token = await subscriber_lock(redis, subscriber_key, _EVENT_CLAIM_TTL)
    if subscriber_token is None:
        if claimed and event_id:
            await redis.delete(_event_lock_key(event_id))
        raise SubscriberBusyError(app_user_id)

    try:
        if (
            event_timestamp_ms is not None
            and event_type in _ORDERED_EVENTS
            and await subscription_service.is_stale_rc_event(
                session, app_user_id, event_timestamp_ms
            )
        ):
            logger.info(
                "RevenueCat stale event ignored type=%s app_user_id=%s event_ts=%s",
                event_type,
                app_user_id,
                event_timestamp_ms,
            )
            if event_id:
                await redis.set(_done_key(event_id), "1", ex=_EVENT_ID_TTL)
            return

        processed = await _dispatch_event(
            session,
            redis,
            settings,
            payload,
            event_type,
            app_user_id,
            receipt_enqueuer,
        )
        if processed and event_timestamp_ms is not None and event_type in _ORDERED_EVENTS:
            await subscription_service.advance_rc_event_watermark(
                session, app_user_id, event_timestamp_ms
            )
            if event_type == "TRANSFER":
                await _advance_transfer_watermarks(session, payload, event_timestamp_ms)
        if processed and event_id:
            await redis.set(_done_key(event_id), "1", ex=_EVENT_ID_TTL)
    finally:
        await release_lock(redis, subscriber_key, subscriber_token)
        if claimed and event_id:
            await redis.delete(_event_lock_key(event_id))
