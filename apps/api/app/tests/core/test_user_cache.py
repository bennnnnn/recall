"""The per-process user cache that authenticated requests read (core/user_cache.py)."""

import time
from uuid import uuid4

from sqlalchemy.orm import make_transient_to_detached

from app.core import user_cache
from app.models.orm import User


def _user() -> User:
    row = User(id=uuid4(), email="someone@example.com", name="Someone")
    make_transient_to_detached(row)
    return row


def test_user_cache_forgets_users_nobody_reads_again(monkeypatch):
    """Every user who ever signed in used to stay cached for the life of the
    process: an entry left only when that user was read again after the TTL."""
    user_cache.clear()
    now = [time.monotonic()]
    monkeypatch.setattr(user_cache._user_cache, "clock", lambda: now[0])
    for _ in range(50):
        user_cache.remember_user(_user())
    now[0] += user_cache.USER_CACHE_TTL_SECONDS + 1
    latest = _user()
    user_cache.remember_user(latest)

    assert user_cache.size() == 1
    cached = user_cache.cached_user(latest.id)
    assert cached is not None
    assert cached.id == latest.id
    user_cache.forget_user(latest.id)
    assert user_cache.cached_user(latest.id) is None
