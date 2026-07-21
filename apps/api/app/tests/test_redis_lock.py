"""Token-safe Redis lock refresh / release."""

from __future__ import annotations

import pytest

from app.core.redis_lock import acquire_lock, refresh_lock, release_lock


@pytest.mark.asyncio
async def test_refresh_lock_extends_only_for_owner(fake_redis):
    token = await acquire_lock(fake_redis, "k", 2)
    assert token is not None
    assert await refresh_lock(fake_redis, "k", token, 30) is True
    assert await refresh_lock(fake_redis, "k", "not-the-owner", 30) is False
    assert await fake_redis.get("k") == token


@pytest.mark.asyncio
async def test_stale_holder_cannot_release_new_owner(fake_redis):
    first = await acquire_lock(fake_redis, "k", 60)
    assert first is not None
    await fake_redis.delete("k")
    second = await acquire_lock(fake_redis, "k", 60)
    assert second is not None
    assert second != first
    await release_lock(fake_redis, "k", first)
    assert await fake_redis.get("k") == second
    await release_lock(fake_redis, "k", second)
    assert await fake_redis.get("k") is None


@pytest.mark.asyncio
async def test_memory_write_lock_stale_release_is_noop(fake_redis):
    from uuid import uuid4

    from app.services import memory as memory_service

    user_id = uuid4()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(memory_service, "get_redis_client", lambda: fake_redis)
        first = await memory_service.acquire_memory_write_lock(user_id)
        assert first is not None
        await fake_redis.delete(f"memwrite:{user_id}")
        second = await memory_service.acquire_memory_write_lock(user_id)
        assert second is not None
        await memory_service.release_memory_write_lock(user_id, first)
        assert await fake_redis.get(f"memwrite:{user_id}") == second
        await memory_service.release_memory_write_lock(user_id, second)
        assert await fake_redis.get(f"memwrite:{user_id}") is None
