"""The per-process user cache that authenticated requests read (core/user_cache.py).

A copy is served only under the generation it was loaded at; a committed write
publishes a new generation in Redis, so every machine drops its copy at once.
"""

import time
from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import make_transient_to_detached

from app.core import user_cache
from app.core.cache_generation import MISSING_GENERATION, generation_from
from app.models.orm import User


def _user(name: str = "Someone") -> User:
    row = User(id=uuid4(), email="someone@example.com", name=name)
    make_transient_to_detached(row)
    return row


@pytest.fixture(autouse=True)
def _empty_cache():
    user_cache.clear()
    yield
    user_cache.clear()


def test_user_cache_forgets_users_nobody_reads_again(monkeypatch):
    """Every user who ever signed in used to stay cached for the life of the
    process: an entry left only when that user was read again after the TTL."""
    now = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    for _ in range(50):
        user_cache.remember_user(_user(), MISSING_GENERATION)
    now[0] += user_cache.USER_CACHE_TTL_SECONDS + 1
    latest = _user()
    user_cache.remember_user(latest, MISSING_GENERATION)

    assert user_cache.size() == 1
    cached = user_cache.cached_user(latest.id, MISSING_GENERATION)
    assert cached is not None
    assert cached.id == latest.id
    user_cache.forget_user(latest.id)
    assert user_cache.cached_user(latest.id, MISSING_GENERATION) is None


def test_a_copy_is_served_only_under_the_generation_it_was_loaded_at():
    user = _user()
    user_cache.remember_user(user, "a1")

    assert user_cache.cached_user(user.id, "a1") is not None
    # Another machine saved a change: the generation every request reads moved on.
    assert user_cache.cached_user(user.id, "b2") is None


def test_each_caller_gets_its_own_copy():
    user = _user()
    user_cache.remember_user(user, "a1")

    first = user_cache.cached_user(user.id, "a1")
    second = user_cache.cached_user(user.id, "a1")

    assert first is not None and second is not None
    assert first is not second
    first.name = "Changed by one request"
    assert second.name == "Someone"


async def test_publish_change_drops_the_copy_and_moves_the_generation(user_generation_redis):
    user = _user()
    user_cache.remember_user(user, MISSING_GENERATION)

    generation = await user_cache.publish_change(user.id)

    stored = await user_generation_redis.get(user_cache.generation_key(user.id))
    assert generation is not None
    assert generation_from(stored) == generation != MISSING_GENERATION
    assert user_cache.cached_user(user.id, MISSING_GENERATION) is None


async def test_publish_change_without_redis_still_drops_the_copy(user_generation_redis):
    user = _user()
    user_cache.remember_user(user, MISSING_GENERATION)

    async def down(*_args, **_kwargs):
        raise RedisConnectionError("down")

    user_generation_redis.set = down

    assert await user_cache.publish_change(user.id) is None
    assert user_cache.cached_user(user.id, MISSING_GENERATION) is None
