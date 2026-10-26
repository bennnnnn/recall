"""Carry today's limits from a deleted account to a new one for the same sign-in.

Quota counters are keyed by user id, so deleting an account and signing in
again with the same Google or Apple login would otherwise start every daily
cap, and this month's live talk minutes, from zero.

Account delete stores what the account had used in one Redis key per sign-in
identity, ``quota_carry:<HMAC-SHA256(jwt_secret, "google:<sub>")>``: never the
raw provider subject, never the user id (so the account's Redis sweep, which
deletes every key naming the user id, leaves it). It expires when the UTC
month ends. When sign-in creates a new user for that identity, the new
account's counters are raised to the stored ones and the key is deleted.

Both sides fail closed. A delete whose counters cannot be stored is refused with
``RedisUnavailableError`` (503 ``unavailable``), before anything is undone, and the phone
asks for a retry. A new account whose snapshot cannot be read or applied is not made:
sign-in answers 503 ``sign_in_unavailable`` and its retry restores. Both were
best-effort, so Redis failing at either step started the same sign-in from zero.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import math
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.models.orm import User
from app.services import quota as quota_service

logger = logging.getLogger(__name__)

CARRY_KEY_PREFIX = "quota_carry:"
# The snapshot only matters until the UTC month ends (live talk is monthly).
_MAX_TTL_SECONDS = 35 * 24 * 60 * 60


def carry_key(settings: Settings, provider: str, sub: str) -> str:
    digest = hmac.new(
        settings.jwt_secret.encode(),
        f"quota-carry:{provider}:{sub}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{CARRY_KEY_PREFIX}{digest}"


def _identities(user: User) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for provider, sub in (("google", user.google_sub), ("apple", user.apple_sub)):
        if isinstance(sub, str) and sub.strip():
            found.append((provider, sub))
    return found


def _ttl_seconds(now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    left = (quota_service.next_month_start(current) - current).total_seconds()
    return max(1, min(_MAX_TTL_SECONDS, math.ceil(left)))


async def save_on_delete(redis: Redis, settings: Settings, user: User) -> None:
    """Keep the account's used counters for its sign-in identities.

    Raises ``RedisUnavailableError`` when they cannot be read or stored: the delete is
    refused rather than lose them (``lifecycle.delete_account`` calls this first).
    """
    identities = _identities(user)
    if not identities:
        return
    try:
        carried = await quota_service.read_carried_usage(redis, user.id)
        if carried.is_empty():
            return
        payload = carried.model_dump_json()
        ttl = _ttl_seconds()
        for provider, sub in identities:
            await redis.set(carry_key(settings, provider, sub), payload, ex=ttl)
    except (RedisError, OSError) as exc:
        logger.warning("Quota carry-over save failed user_id=%s", user.id, exc_info=True)
        raise RedisUnavailableError() from exc


async def restore_for_new_account(
    redis: Redis,
    settings: Settings,
    user_id: UUID,
    *,
    provider: str,
    sub: str,
) -> str | None:
    """Raise a just-created, not yet committed account's counters to its identity's snapshot.

    Returns the snapshot's key for ``drop_restored`` once the account commits, or None when
    there is none: one GET, the common case. Raises ``RedisUnavailableError`` when the
    snapshot cannot be read or applied, so sign-in refuses and makes no account (the next
    sign-in would find the account and never restore). The snapshot stays for the retry.
    """
    key = carry_key(settings, provider, sub)
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        try:
            carried = quota_service.CarriedUsage.model_validate_json(raw)
        except ValidationError:
            logger.warning("Quota carry-over snapshot unreadable; dropped")
        else:
            await quota_service.apply_carried_usage(redis, user_id, carried)
    except (RedisError, OSError) as exc:
        logger.warning("Quota carry-over restore failed user_id=%s", user_id, exc_info=True)
        raise RedisUnavailableError() from exc
    return key


async def drop_restored(redis: Redis, key: str) -> None:
    """Delete a snapshot a committed account took. Best effort, never raises: the counters
    are raised already, and a snapshot left over only raises a later account's counters
    (raise-only, never lowered) until it expires with the month."""
    try:
        await redis.delete(key)
    except Exception:
        logger.warning("Quota carry-over snapshot not dropped; it expires", exc_info=True)
