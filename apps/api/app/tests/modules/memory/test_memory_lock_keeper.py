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
from app.modules.memory import repository as memories_repo
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


def _holder(name: str, order: list[str]) -> tuple[Any, list[Any]]:
    """A holder's call and the patches that record its lock's take, keep, stop and release.

    Extraction, consolidation and learning progress import the lock's functions; instruct
    and the hand edits call them through ``locks``. Each runs its shortest path: the user
    gone, memory off, nothing deleted."""
    from app.core.config import Settings
    from app.modules.memory import (
        consolidation_workflow,
        crud,
        extraction_workflow,
        instruct,
        learning_progress,
    )

    keeper = MagicMock()

    def keep(_user_id: Any, token: Any) -> Any:
        order.append(f"keep:{token}")
        return keeper

    def stop(kept: Any) -> None:
        order.append(f"stop:{kept is keeper}")

    release = AsyncMock(side_effect=lambda *_args: order.append("release"))
    common: dict[str, Any] = {"keep_memory_write_lock": keep, "stop_keeping": stop}
    common["release_memory_write_lock"] = release
    gone = patch.object(users_repo, "get_by_id", AsyncMock(return_value=None))
    settings, user_id = Settings(), uuid4()
    if name in ("extraction", "consolidation", "learning progress"):
        module = {
            "extraction": extraction_workflow,
            "consolidation": consolidation_workflow,
            "learning progress": learning_progress,
        }[name]
        taken: dict[str, Any] = {
            "acquire_memory_write_lock": AsyncMock(return_value="tok"),
            **common,
        }
        patches = [patch.multiple(module, **taken), patch.object(module, "SessionLocal"), gone]
        call = {
            "extraction": lambda: extraction_workflow.extract_and_store_memories(
                settings, user_id=user_id, chat_id=uuid4(), transcript="I live in Denver."
            ),
            "consolidation": lambda: consolidation_workflow.consolidate_user_memory_sections(
                settings, user_id=user_id
            ),
            "learning progress": lambda: learning_progress.record_learning_progress(
                settings, user_id=user_id, chat_id=uuid4(), text="Learning X", started_at=None
            ),
        }[name]
        return call, patches
    if name == "instruct":
        taken = {"take_memory_write_lock": AsyncMock(return_value="tok"), **common}
        off = AsyncMock(return_value=MagicMock(memory_enabled=False))
        patches = [
            patch.multiple(locks, **taken),
            patch.object(instruct, "SessionLocal"),
            patch.object(instruct, "load_memory_snapshot", off),
        ]

        async def ask() -> None:
            with pytest.raises(instruct.MemoryOffError):
                await instruct.apply_memory_instruction(
                    settings, user_id=user_id, instruction="forget my city"
                )

        return ask, patches
    taken = {
        "acquire_memory_write_lock_or_raise": AsyncMock(return_value="tok"),
        **common,
    }
    patches = [
        patch.multiple(locks, **taken),
        patch.object(memories_repo, "delete_by_id", AsyncMock(return_value=0)),
    ]
    return lambda: crud.delete_memory(AsyncMock(), user_id, uuid4()), patches


@pytest.mark.parametrize(
    "holder", ["extraction", "consolidation", "learning progress", "instruct", "hand edit"]
)
async def test_every_holder_keeps_the_lock_while_it_works(holder: str) -> None:
    """Each holder takes, keeps, stops keeping, then releases the lock, on every path."""
    from contextlib import ExitStack

    order: list[str] = []
    call, patches = _holder(holder, order)
    with ExitStack() as stack:
        for each in patches:
            stack.enter_context(each)
        await call()

    assert order == ["keep:tok", "stop:True", "release"]
