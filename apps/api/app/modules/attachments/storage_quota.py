"""How much an account keeps in its Library, against its plan's total.

Daily upload counts cap how fast files arrive, not how many stay: a free
account could keep about 4.5 GB more every month, forever. Every attachment row
is real stored bytes (a resend copies the object, ``reuse.py``), generated
pictures included, so the total is one SUM over the user's rows
(``ix_attachments_user``). A web lookup's reference photos are part of their message,
never a Library item, and are left out (owner, 2026-11-24): the server picks them, so they
do not grow with what the user sends. A resend's copy (hidden from Library, a full copy of
the bytes) still counts: Pro has no daily message cap, and resending one file message after
message would otherwise store without limit; it goes when its chat is deleted. A
pending upload counts from its presign. An account's presigns run one at a time
(``library_presign``): two that raced the read both passed, and with photo uploads no
longer counted a day, a burst of them could have gone well past the total.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.redis_lock import acquire_lock, release_lock
from app.exceptions import DomainError, RedisUnavailableError
from app.models.orm import Attachment, User
from app.modules.billing.entitlements import allowance
from app.services.quota.messages import plan_message

STORAGE_FULL_MESSAGE_FREE = (
    "Your Library is full. Delete files you no longer need, or upgrade for more room."
)
STORAGE_FULL_MESSAGE_PAID = "Your Library is full. Delete files you no longer need to make room."


# A reference photo a web lookup found (``search``) is part of its message, never a Library
# item: it is not counted against the plan's total (owner, 2026-11-24).
_NOT_STORED_SOURCES = ("search",)


async def stored_bytes(session: AsyncSession, user_id: UUID) -> int:
    """Bytes in the user's attachment rows, pending uploads and resend copies included,
    lookup photos not."""
    total = await session.scalar(
        select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
            Attachment.user_id == user_id,
            Attachment.source.not_in(_NOT_STORED_SOURCES),
        )
    )
    return int(total or 0)


async def has_room_for(
    session: AsyncSession, settings: Settings, user: User, size_bytes: int
) -> bool:
    """True when *size_bytes* more still fits in the user's plan's Library total."""
    cap = allowance(user, "library_storage_bytes", settings)
    return await stored_bytes(session, user.id) + size_bytes <= cap


# Held across one presign (a read, a signature, an insert); expires on its own if the
# request dies holding it. A presign waits its turn for up to ``PRESIGN_WAIT_SECONDS``.
_LOCK_SECONDS = 15
PRESIGN_WAIT_SECONDS = 5.0
_POLL_SECONDS = 0.05


@asynccontextmanager
async def library_presign(redis: Redis, user_id: UUID) -> AsyncIterator[None]:
    """One presign at a time for *user_id*: its Library total read and the pending row
    that adds to it happen together. 429 ``rate_limited`` when the turn never comes."""
    key = f"recall:library_presign:{user_id}"
    try:
        token = await acquire_lock(redis, key, _LOCK_SECONDS)
        waited = 0.0
        while token is None and waited < PRESIGN_WAIT_SECONDS:
            await asyncio.sleep(_POLL_SECONDS)
            waited += _POLL_SECONDS
            token = await acquire_lock(redis, key, _LOCK_SECONDS)
    except RedisError as exc:
        # Any Redis refusal (down, over its request quota, read-only) is the outage's 503.
        raise RedisUnavailableError() from exc
    if token is None:
        raise DomainError(
            "Too many uploads at once. Try again in a moment.",
            status_code=429,
            code="rate_limited",
        )
    try:
        yield
    finally:
        await release_lock(redis, key, token)


async def library_storage(session: AsyncSession, settings: Settings, user: User) -> tuple[int, int]:
    """(bytes kept, the plan's total): the same sum and total the presign checks."""
    cap = allowance(user, "library_storage_bytes", settings)
    return await stored_bytes(session, user.id), cap


def storage_full_message(user: User) -> str:
    return plan_message(user, free=STORAGE_FULL_MESSAGE_FREE, paid=STORAGE_FULL_MESSAGE_PAID)
