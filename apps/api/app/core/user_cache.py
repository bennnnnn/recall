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

from uuid import UUID

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import make_transient_to_detached

from app.core.ttl_cache import TtlCache
from app.models.orm import User

USER_CACHE_TTL_SECONDS = 60.0
# Users seen on one process within the TTL; far above normal traffic.
_USER_CACHE_MAX_ENTRIES = 5_000
_user_cache: TtlCache[UUID, User] = TtlCache(
    ttl_seconds=USER_CACHE_TTL_SECONDS,
    max_entries=_USER_CACHE_MAX_ENTRIES,
)


def cached_user(user_id: UUID) -> User | None:
    return _user_cache.get(user_id)


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


def forget_user(user_id: UUID) -> None:
    _user_cache.pop(user_id)


def clear() -> None:
    """Drop every entry (tests)."""
    _user_cache.clear()


def size() -> int:
    return len(_user_cache)
