"""This process's copies of recently loaded users, checked against a generation in Redis.

Every authenticated request and every chat turn needs the user row, and Neon is a
round trip or more away, so the last loaded row stays here. Each committed write
to a user row stores a new generation for that user in Redis (``publish_change``),
and each request reads the current one in the same MGET as its token check
(``core/access_tokens.check_access``). A copy is used only under the generation it
was loaded at, so a plan change from the RevenueCat webhook, a settings, memory or
preferences change, or consent saved on any machine applies to the next request
and the next chat turn on every machine.

The TTL only bounds a copy whose change never reached Redis (Redis down at that
moment, or the process died between the commit and the publish).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, make_transient_to_detached

from app.core.background_tasks import create_background_task
from app.core.cache_generation import bump_generation
from app.core.redis import get_redis_client
from app.core.ttl_cache import TtlCache
from app.models.orm import User

logger = logging.getLogger(__name__)

USER_CACHE_TTL_SECONDS = 300.0
# Users seen on one process within the TTL; far above normal traffic.
_USER_CACHE_MAX_ENTRIES = 5_000
_GENERATION_PREFIX = "usergen:"
_user_cache: TtlCache[UUID, tuple[User, str]] = TtlCache(
    ttl_seconds=USER_CACHE_TTL_SECONDS,
    max_entries=_USER_CACHE_MAX_ENTRIES,
)


def generation_key(user_id: UUID) -> str:
    return f"{_GENERATION_PREFIX}{user_id}"


def _snapshot(user: User) -> User:
    """Detached copy safe to merge into a later request session."""
    state = sa_inspect(user)
    # In-memory dict only. getattr on an expired column lazy-loads and raises
    # MissingGreenlet from an async session.
    values = {key: state.dict[key] for key in state.mapper.columns.keys() if key in state.dict}
    snap = User(**values)
    make_transient_to_detached(snap)
    return snap


def cached_user(user_id: UUID, generation: str) -> User | None:
    """A private copy of the row loaded under ``generation`` (the current one), or None."""
    hit = _user_cache.get(user_id)
    if hit is None or hit[1] != generation:
        return None
    user = hit[0]
    return _snapshot(user) if isinstance(user, User) else user


def remember_user(user: User, generation: str) -> None:
    """Keep ``user`` as read under ``generation``, read before the row was."""
    cached = _snapshot(user) if isinstance(user, User) else user
    _user_cache.put(user.id, (cached, generation))


async def publish_change(user_id: UUID) -> str | None:
    """After a committed write: drop this copy and give every machine a new generation.

    Returns the new generation, under which a row read from now on may be kept;
    None when Redis did not take it (other machines keep their copy until the TTL).
    """
    forget_user(user_id)
    try:
        return await bump_generation(get_redis_client(), generation_key(user_id))
    except Exception:
        logger.warning("User generation bump failed user_id=%s", user_id, exc_info=True)
        return None


def publish_change_after_commit(session: Session, user_id: UUID) -> None:
    """``publish_change`` once ``session`` commits; just drop this copy if it rolls back.

    Until the commit the change is not saved, and a rollback must not leave this
    process serving it. The publish runs on its own task right after the commit
    (this hook cannot await).
    """
    settled = False

    def settle(committed: bool) -> None:
        nonlocal settled
        if settled:
            return
        settled = True
        forget_user(user_id)
        if committed:
            create_background_task(publish_change(user_id), name="user_generation_bump")

    event.listen(session, "after_commit", lambda _session: settle(True), once=True)
    # Soft too: any rollback, a savepoint's included, may have undone the write.
    event.listen(
        session, "after_soft_rollback", lambda _session, _previous: settle(False), once=True
    )


def forget_user(user_id: UUID) -> None:
    _user_cache.pop(user_id)


def clear() -> None:
    """Drop every entry (tests)."""
    _user_cache.clear()


def size() -> int:
    return len(_user_cache)
