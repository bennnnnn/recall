"""Apply the user's own memory edits ("keep lists under five things")."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.modules.memory import llm as memory_llm
from app.modules.memory import repository as memories_repo
from app.modules.memory.apply import apply_memory_facts
from app.modules.memory.extraction_workflow import load_memory_snapshot, writes_from_ops
from app.modules.memory.topics import parse_topic

logger = logging.getLogger(__name__)


class MemoryOffError(Exception):
    """Memory is turned off for this account."""


class MemoryInstructionFailedError(Exception):
    """The model could not turn the instruction into edits."""


@dataclass(frozen=True)
class MemoryInstructionOutcome:
    applied: int
    reply: str


async def apply_memory_instruction(
    settings: Settings,
    *,
    user_id: UUID,
    instruction: str,
    focus_topic: str | None = None,
) -> MemoryInstructionOutcome:
    """Edit memory as the user asked. Raises MemoryWriteLockBusyError while memory is busy."""
    from app.modules import memory as memory_service

    lock_token = await memory_service.acquire_memory_write_lock(user_id)
    if not lock_token:
        raise memory_service.MemoryWriteLockBusyError(user_id)
    try:
        # Short session: nothing stays open while the model works.
        async with SessionLocal() as session:
            snapshot = await load_memory_snapshot(session, user_id)
        if not snapshot.memory_enabled:
            raise MemoryOffError()
        result = await memory_llm.instruct_memory(
            settings,
            instruction,
            existing_facts=snapshot.prompt_facts,
            existing_areas=snapshot.prompt_areas,
            focus_topic=parse_topic(focus_topic),
        )
        if result is None:
            raise MemoryInstructionFailedError()
        # The user asked for this change, so it is saved like "remember this":
        # sensitive topics included and no confidence floor.
        writes, _ = writes_from_ops(
            result.ops,
            chat_id=None,
            explicit_remember=True,
            include_sensitive=snapshot.include_sensitive,
            min_confidence=0.0,
            transcript=f"User: {instruction}",
            existing_texts=snapshot.existing_facts.values(),
        )
        if writes:
            await apply_memory_facts(
                settings,
                user_id=user_id,
                writes=writes,
                session_factory=SessionLocal,
                memories=memories_repo,
                expected_facts=snapshot.existing_facts,
                manual_edit=True,
            )
        logger.info("memory_instruction user_id=%s applied=%s", user_id, len(writes))
        return MemoryInstructionOutcome(applied=len(writes), reply=result.reply.strip())
    finally:
        await memory_service.release_memory_write_lock(user_id, lock_token)
