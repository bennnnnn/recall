from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.schemas import MemoryFactOp, MemoryFactUpdateResult
from app.modules import memory as memory_service
from app.modules.memory import instruct as instruct_service
from app.modules.memory.extraction_workflow import MemorySnapshot
from app.modules.memory.writes_repository import MemoryFactWrite


class _SessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return None


def _snapshot(*, enabled: bool = True) -> MemorySnapshot:
    fact_id = uuid4()
    return MemorySnapshot(
        memory_enabled=enabled,
        include_sensitive=False,
        existing_facts={fact_id: "User likes tea"},
        prompt_facts=[
            {"id": str(fact_id), "type": "fact", "topic": "notes", "text": "User likes tea"}
        ],
        prompt_areas=[{"topic": "area:recall", "title": "Recall", "summary": ""}],
    )


@contextmanager
def _patches(*, result, snapshot=None, lock="token"):
    apply = AsyncMock()
    instruct = AsyncMock(return_value=result)
    release = AsyncMock()
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(memory_service, "acquire_memory_write_lock", AsyncMock(return_value=lock))
        )
        stack.enter_context(patch.object(memory_service, "release_memory_write_lock", release))
        stack.enter_context(
            patch("app.modules.memory.instruct.SessionLocal", MagicMock(side_effect=_SessionCM))
        )
        stack.enter_context(
            patch(
                "app.modules.memory.instruct.load_memory_snapshot",
                AsyncMock(return_value=snapshot or _snapshot()),
            )
        )
        stack.enter_context(
            patch("app.modules.memory.instruct.memory_llm.instruct_memory", instruct)
        )
        stack.enter_context(patch("app.modules.memory.instruct.apply_memory_facts", apply))
        yield apply, instruct, release


@pytest.mark.asyncio
async def test_an_instruction_is_saved_like_remember_this():
    result = MemoryFactUpdateResult(
        ops=[
            MemoryFactOp(
                op="add",
                type="fact",
                topic="preferences",
                text="User wants lists under five items.",
                confidence=0.3,
            ),
            MemoryFactOp(
                op="add",
                type="fact",
                topic="notes",
                text="User has been dating Sam.",
                confidence=0.9,
                sensitivity="relationship",
            ),
        ],
        reply="Saved two things.",
    )
    with _patches(result=result) as (apply, instruct, release):
        outcome = await instruct_service.apply_memory_instruction(
            Settings(),
            user_id=uuid4(),
            instruction="Keep lists under five things, and remember I'm dating Sam",
            focus_topic="Preferences",
        )

    assert outcome.applied == 2
    assert outcome.reply == "Saved two things."
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    # Low confidence and a sensitive topic both pass: the user asked for them.
    assert [(write.topic, write.type) for write in writes] == [
        ("preferences", "preference"),
        ("notes", "fact"),
    ]
    # A hand edit: if it changes saved facts, the history scan skips older lines.
    assert apply.await_args.kwargs["manual_edit"] is True
    assert instruct.await_args.kwargs["focus_topic"] == "preferences"
    assert instruct.await_args.kwargs["existing_areas"][0]["topic"] == "area:recall"
    release.assert_awaited_once()


@pytest.mark.asyncio
async def test_an_instruction_with_nothing_to_change_only_replies():
    result = MemoryFactUpdateResult(ops=[], reply="That isn't something to remember.")
    with _patches(result=result) as (apply, _, _release):
        outcome = await instruct_service.apply_memory_instruction(
            Settings(), user_id=uuid4(), instruction="What's the weather?"
        )
    assert outcome.applied == 0
    assert outcome.reply == "That isn't something to remember."
    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failed_model_call_raises_and_releases_the_lock():
    with _patches(result=None) as (apply, _, release):
        with pytest.raises(instruct_service.MemoryInstructionFailedError):
            await instruct_service.apply_memory_instruction(
                Settings(), user_id=uuid4(), instruction="Remember I like tea"
            )
    apply.assert_not_awaited()
    release.assert_awaited_once()


@pytest.mark.asyncio
async def test_memory_off_raises_before_calling_the_model():
    with _patches(result=None, snapshot=_snapshot(enabled=False)) as (_, instruct, _release):
        with pytest.raises(instruct_service.MemoryOffError):
            await instruct_service.apply_memory_instruction(
                Settings(), user_id=uuid4(), instruction="Remember I like tea"
            )
    instruct.assert_not_awaited()


@pytest.mark.asyncio
async def test_busy_memory_raises_without_calling_the_model():
    with _patches(result=None, lock=None) as (_, instruct, release):
        with pytest.raises(memory_service.MemoryWriteLockBusyError):
            await instruct_service.apply_memory_instruction(
                Settings(), user_id=uuid4(), instruction="Remember I like tea"
            )
    instruct.assert_not_awaited()
    release.assert_not_awaited()
