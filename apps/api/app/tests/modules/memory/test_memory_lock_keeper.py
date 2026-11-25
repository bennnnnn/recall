"""The memory write lock lasts as long as its holder works (audit, 2026-11-25).

Its fixed 150 s TTL was shorter than the model work under it: consolidation merges pair
after pair, each call up to a minute, so the lock expired mid-pass and a second writer
(an extraction, a hand edit) wrote over the same facts. A holder now refreshes it; one
that dies still frees it after one TTL.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.memory import locks
from app.repositories import users as users_repo


@pytest.fixture
def short_lock(monkeypatch: pytest.MonkeyPatch, fake_redis: Any) -> Any:
    monkeypatch.setattr(locks, "_MEMORY_WRITE_LOCK_TTL", 1)
    monkeypatch.setattr(locks, "_MEMORY_WRITE_LOCK_REFRESH_SECONDS", 0.2)
    monkeypatch.setattr(locks, "get_redis_client", lambda: fake_redis)
    return fake_redis


@pytest.mark.wall_clock
async def test_a_holder_at_work_keeps_the_lock_past_its_ttl(short_lock: Any) -> None:
    user_id = uuid4()
    token = await locks.take_memory_write_lock(user_id)
    keeper = locks.keep_memory_write_lock(user_id, token)
    try:
        await asyncio.sleep(1.6)
        # Still this holder's: no second writer gets in.
        assert await locks.take_memory_write_lock(user_id) is None
        assert await short_lock.get(locks.memory_write_lock_key(user_id)) == token
    finally:
        locks.stop_keeping(keeper)
        await locks.release_memory_write_lock(user_id, token)
    assert await locks.take_memory_write_lock(user_id) is not None


@pytest.mark.wall_clock
async def test_a_holder_that_stopped_frees_the_lock_after_one_ttl(short_lock: Any) -> None:
    user_id = uuid4()
    token = await locks.take_memory_write_lock(user_id)
    keeper = locks.keep_memory_write_lock(user_id, token)
    locks.stop_keeping(keeper)
    await asyncio.sleep(1.3)
    assert await locks.take_memory_write_lock(user_id) is not None


async def test_consolidation_keeps_the_lock_while_it_merges() -> None:
    """The pass that runs one model call per pair holds a keeper from take to release."""
    from app.core.config import Settings
    from app.modules.memory import consolidation_workflow as workflow

    order: list[str] = []
    keeper = MagicMock()

    def keep(_user_id: Any, token: Any) -> Any:
        order.append(f"keep:{token}")
        return keeper

    with (
        patch.object(workflow, "acquire_memory_write_lock", AsyncMock(return_value="tok")),
        patch.object(workflow, "keep_memory_write_lock", keep),
        patch.object(workflow, "stop_keeping", lambda k: order.append(f"stop:{k is keeper}")),
        patch.object(
            workflow,
            "release_memory_write_lock",
            AsyncMock(side_effect=lambda *_args: order.append("release")),
        ),
        patch.object(users_repo, "get_by_id", AsyncMock(return_value=None)),
        patch.object(workflow, "SessionLocal", MagicMock()),
    ):
        await workflow.consolidate_user_memory_sections(Settings(), user_id=uuid4())

    assert order == ["keep:tok", "stop:True", "release"]
