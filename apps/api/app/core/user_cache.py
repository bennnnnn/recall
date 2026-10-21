"""This process's cache of recently loaded users, read by every authenticated request.

Neon from a laptop is a few hundred milliseconds per checkout. Chat auth runs
on every send, so the last loaded user stays here and the next request skips
that round trip. Profile edits are rare; a short TTL is enough.

Per machine by design: a write on one machine refreshes or drops its own entry
only, so another ``app`` machine can serve the old row for up to the TTL
(``docs/SCALING.md``). A shared cache or a cross-machine invalidation would
replace this module and keep its three functions.
"""

from __future__ import annotations

import logging
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, make_transient_to_detached

from app.core.redis_counters import incr_with_ttl
from app.core.ttl_cache import TtlCache
from app.models.orm import User

logger = logging.getLogger(__name__)

USER_CACHE_TTL_SECONDS = 60.0
# Users seen on one process within the TTL; far above normal traffic.
_USER_CACHE_MAX_ENTRIES = 5_000
_user_cache: TtlCache[UUID, User] = TtlCache(
    ttl_seconds=USER_CACHE_TTL_SECONDS,
    max_entries=_USER_CACHE_MAX_ENTRIES,
)


# A per-user counter in Redis that every privacy-relevant profile write bumps (consent,
# memory, web search). An entry cached at generation N is stale on every machine once the
# counter moves, so a withdrawal is honoured at once, not up to a TTL later. A missing
# key reads as 0, which a bumped entry never matches: losing the key only costs a reload.
_GENERATION_KEY = "usergen:{user_id}"
_GENERATION_TTL_SECONDS = 86_400
_generations: TtlCache[UUID, int] = TtlCache(
    ttl_seconds=USER_CACHE_TTL_SECONDS,
    max_entries=_USER_CACHE_MAX_ENTRIES,
)


def cached_user(user_id: UUID) -> User | None:
    return _user_cache.get(user_id)


async def _read_generation(redis: Redis, user_id: UUID) -> int:
    raw = await redis.get(_GENERATION_KEY.format(user_id=user_id))
    return int(raw or 0)


async def note_generation(redis: Redis, user_id: UUID) -> None:
    """Remember which generation the row just cached was read at (best-effort)."""
    try:
        _generations.put(user_id, await _read_generation(redis, user_id))
    except Exception:
        _generations.pop(user_id)
        logger.warning("User generation read failed user_id=%s", user_id, exc_info=True)


async def is_current(redis: Redis, user_id: UUID) -> bool:
    """Whether the cached row is still the account's latest privacy settings.

    A row with no generation noted counts as generation 0, current until the account's
    first privacy write. False when Redis fails: the caller re-reads the row.
    """
    known = _generations.get(user_id) or 0
    try:
        return await _read_generation(redis, user_id) == known
    except Exception:
        logger.warning("User generation check failed user_id=%s", user_id, exc_info=True)
        return False


async def bump_generation(redis: Redis, user_id: UUID) -> None:
    """Mark every machine's cached row stale after a committed profile write."""
    try:
        generation = await incr_with_ttl(
            redis, _GENERATION_KEY.format(user_id=user_id), 1, _GENERATION_TTL_SECONDS
        )
    except Exception:
        # Without the bump, other machines keep the old row until their TTL.
        logger.warning("User generation bump failed user_id=%s", user_id, exc_info=True)
        return
    _generations.put(user_id, generation)


def _snapshot(user: User) -> User:
    """Detached copy safe to merge into a later request session."""
    state = sa_inspect(user)
    # In-memory dict only. getattr on an expired column lazy-loads and raises
    # MissingGreenlet from an async session.
    values = {key: state.dict[key] for key in state.mapper.columns.keys() if key in state.dict}
    snap = User(**values)
    make_transient_to_detached(snap)
    return snap


def remember_user(user: User) -> None:
    cached = _snapshot(user) if isinstance(user, User) else user
    _user_cache.put(user.id, cached)


def remember_user_after_commit(session: Session, user: User) -> None:
    """Cache ``user`` as written once ``session`` commits; drop the entry if it rolls back.

    Until then the change is not saved, and a rollback must not leave this
    process serving it. Dropping (not keeping the old entry) sends the next read
    to the database, which also covers a read that cached the old row meanwhile.
    """
    snapshot = _snapshot(user) if isinstance(user, User) else user
    settled = False

    def settle(committed: bool) -> None:
        nonlocal settled
        if settled:
            return
        settled = True
        if committed:
            _user_cache.put(snapshot.id, snapshot)
        else:
            _user_cache.pop(snapshot.id)

    event.listen(session, "after_commit", lambda _session: settle(True), once=True)
    # Soft too: any rollback, a savepoint's included, may have undone the write.
    event.listen(
        session, "after_soft_rollback", lambda _session, _previous: settle(False), once=True
    )


def forget_user(user_id: UUID) -> None:
    _user_cache.pop(user_id)
    _generations.pop(user_id)


def clear() -> None:
    """Drop every entry (tests)."""
    _user_cache.clear()
    _generations.clear()


def size() -> int:
    return len(_user_cache)
