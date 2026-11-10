"""Answer photos found once and reused for the same lookup.

The model writes short, generic lookups for the photo above an answer ("Ethiopia location
map"). The first one searches, fetches and stores the asker's photo as always; then a copy
goes to a shared area of storage that belongs to no user (``SHARED_PREFIX``), and Redis
records where it is for ``answer_photo_cache_days``. The next lookup of the same words, by
anyone, copies that stored photo into the asker's own attachment: no image search, no fetch
from a third-party host, and nothing charged to the asker's daily lookups or the global
spend.

Privacy: the record's key and the shared copy's name are a hash of the words, never the
words, and the record holds only where the copy is (no user, no query). The asker's own
attachment is named by the asker's own words, as before. Account deletion removes that
attachment like any other; the shared copy is no account's and stays until it ages out
(``sweep_expired``, run by the data retention scheduler).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways.storage_gateway import StorageGateway
from app.modules.attachments.service import StoredImage

logger = logging.getLogger(__name__)

# Shared copies live here, never under a user's ``{user_id}/`` prefix.
SHARED_PREFIX = "shared/answer-photos/"
_RECORD_KEY = "answer_photo_cache:{digest}"
# Every recorded copy, scored by when it was stored, for the sweep.
_STORED_INDEX = "answer_photo_cache:stored"
_DAY_SECONDS = 24 * 60 * 60
# A copy is deleted this long after its record expired: a lookup that read the record
# just before then still finds its bytes.
_SWEEP_MARGIN_SECONDS = 60 * 60
# Copies deleted per sweep at most; the next hourly cycle takes the rest.
_SWEEP_BATCH = 500


@dataclass(frozen=True, slots=True)
class CachedPhoto:
    """Where a shared copy is, and what it is."""

    storage_key: str
    content_type: str
    size_bytes: int


def lookup_digest(query: str) -> str:
    """The lookup's words as one hash: case and spacing do not make a new lookup."""
    normalized = " ".join(query.casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def _max_age_seconds(settings: Settings) -> int:
    return max(0, settings.answer_photo_cache_days) * _DAY_SECONDS


def _parsed(raw: object, *, max_age: int, now: float) -> CachedPhoto | None:
    """The record, when it is one this module wrote and younger than ``max_age``."""
    if not isinstance(raw, str | bytes):
        return None
    try:
        record = json.loads(raw)
        cached = CachedPhoto(
            storage_key=str(record["storage_key"]),
            content_type=str(record["content_type"]),
            size_bytes=int(record["size_bytes"]),
        )
        stored_at = float(record["stored_at"])
    except (ValueError, TypeError, KeyError):
        return None
    if not cached.storage_key.startswith(SHARED_PREFIX) or now - stored_at > max_age:
        return None
    return cached


async def cached_photo(settings: Settings, redis: Redis, query: str) -> CachedPhoto | None:
    """The shared copy recorded for this lookup, or None (none, too old, or Redis down)."""
    max_age = _max_age_seconds(settings)
    if not max_age:
        return None
    try:
        raw = await redis.get(_RECORD_KEY.format(digest=lookup_digest(query)))
    except Exception:
        logger.warning("Answer photo cache read failed", exc_info=True)
        return None
    return _parsed(raw, max_age=max_age, now=time.time())


async def copy_for_user(
    gateway: StorageGateway, redis: Redis, user_id: UUID, query: str, cached: CachedPhoto
) -> StoredImage | None:
    """The user's own copy of a shared photo, written inside storage. None when the shared
    copy is gone: its record is dropped, and the lookup runs as if nothing were kept."""
    presigned = await gateway.presign_upload(
        user_id=str(user_id), content_type=cached.content_type, size_bytes=cached.size_bytes
    )
    if not await gateway.copy_bytes(cached.storage_key, presigned.storage_key):
        await _forget(redis, query)
        return None
    return StoredImage(
        attachment_id=UUID(presigned.attachment_id),
        storage_key=presigned.storage_key,
        content_type=cached.content_type,
        size_bytes=cached.size_bytes,
    )


async def _forget(redis: Redis, query: str) -> None:
    try:
        await redis.delete(_RECORD_KEY.format(digest=lookup_digest(query)))
    except Exception:
        logger.warning("Answer photo cache drop failed", exc_info=True)


async def remember(
    settings: Settings, gateway: StorageGateway, redis: Redis, query: str, photo: StoredImage
) -> None:
    """Keep a shared copy of a photo just found for ``query``, and record it.

    Best-effort and off the reply's path: a failure only means the next lookup searches.
    """
    max_age = _max_age_seconds(settings)
    if not max_age:
        return
    digest = lookup_digest(query)
    shared_key = f"{SHARED_PREFIX}{digest}"
    try:
        if not await gateway.copy_bytes(photo.storage_key, shared_key):
            return
        stored_at = time.time()
        record = {
            "storage_key": shared_key,
            "content_type": photo.content_type,
            "size_bytes": photo.size_bytes,
            "stored_at": stored_at,
        }
        await redis.set(_RECORD_KEY.format(digest=digest), json.dumps(record), ex=max_age)
        await redis.zadd(_STORED_INDEX, {digest: stored_at})
    except Exception:
        logger.warning("Keeping an answer photo for reuse failed", exc_info=True)


async def sweep_expired(
    settings: Settings, gateway: StorageGateway, redis: Redis, *, now: float | None = None
) -> int:
    """Delete shared copies whose record has aged out; how many went.

    A copy stored again since it was listed (the same lookup, after its record expired)
    keeps its newer time in the index and is left alone.
    """
    cutoff = (time.time() if now is None else now) - _max_age_seconds(settings)
    cutoff -= _SWEEP_MARGIN_SECONDS
    listed = await redis.zrangebyscore(_STORED_INDEX, "-inf", cutoff, start=0, num=_SWEEP_BATCH)
    deleted = 0
    for member in listed:
        digest = member.decode() if isinstance(member, bytes) else str(member)
        stored_at = await redis.zscore(_STORED_INDEX, digest)
        if stored_at is not None and stored_at > cutoff:
            continue
        try:
            await gateway.delete_bytes(f"{SHARED_PREFIX}{digest}")
        except Exception:
            logger.warning("Deleting an aged answer photo failed", exc_info=True)
            continue
        await redis.zrem(_STORED_INDEX, digest)
        deleted += 1
    if deleted:
        logger.info("Answer photo cache swept deleted=%s", deleted)
    return deleted
