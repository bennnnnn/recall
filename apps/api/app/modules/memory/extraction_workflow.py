"""Extract and persist atomic memory facts from a chat transcript."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.modules.memory import (
    acquire_memory_write_lock,
    is_explicit_forget_command,
    is_explicit_memory_command,
    is_memory_candidate,
    release_memory_write_lock,
)
from app.modules.memory import llm as memory_llm
from app.modules.memory import repository as memories_repo
from app.modules.memory.apply import apply_memory_facts
from app.modules.memory.commands import (
    forget_requests,
    is_explicit_mute_command,
    is_memory_correction,
    memory_reset_request,
    mute_requests,
)
from app.modules.memory.extract_backlog import (
    clear_failed_extract_passes,
    expand_memory_extract_transcript,
    history_chat_transcript,
    note_failed_extract_pass,
    stamp_extract_cursor,
)
from app.modules.memory.fact_quality import FactView, is_one_off_schedule_fact, texts_to_drop
from app.modules.memory.facts import should_skip_sensitive_persist
from app.modules.memory.forget_match import phrase_names_fact
from app.modules.memory.name_claim import is_unclaimed_user_name
from app.modules.memory.ops import EXPLICIT_IMPORTANCE, MODEL_IMPORTANCE_MAX
from app.modules.memory.self_facts import stated_fact_writes
from app.modules.memory.switch import memory_switch_on
from app.modules.memory.text import (
    classify_memory_sensitivity,
    normalize_memory_text,
)
from app.modules.memory.topics import (
    fact_topic,
    is_area,
    parse_topic,
    topic_memory_type,
)
from app.modules.memory.writes_repository import MemoryFactWrite
from app.repositories import users as users_repo

logger = logging.getLogger(__name__)

# ``skipped_lock``: memory was busy, retry after a backoff. ``model_failed``: the
# model gave no usable answer, so these lines were not read.
ExtractOutcome = Literal["skipped_lock", "model_failed"] | None
_MATCH_ONLY_OPS = frozenset({"delete", "mute"})


@dataclass(frozen=True)
class MemorySnapshot:
    memory_enabled: bool
    include_sensitive: bool
    existing_facts: dict[UUID, str]
    prompt_facts: list[dict[str, str]]
    prompt_areas: list[dict[str, str]]
    # When the user last removed or changed memory by hand.
    edited_at: datetime | None = None
    active_facts: tuple[FactView, ...] = ()


async def load_memory_snapshot(
    session: AsyncSession,
    user_id: UUID,
) -> MemorySnapshot:
    user = await users_repo.get_by_id(session, user_id)
    if user is None or not memory_switch_on(user):
        return MemorySnapshot(
            memory_enabled=False,
            include_sensitive=False,
            existing_facts={},
            prompt_facts=[],
            prompt_areas=[],
        )
    existing = await memories_repo.list_for_user(
        session, user_id, include_muted=False, include_superseded=False
    )
    areas = await memories_repo.list_areas(session, user_id)
    return MemorySnapshot(
        memory_enabled=True,
        include_sensitive=user.memory_include_sensitive,
        existing_facts={memory.id: memory.text for memory in existing},
        prompt_facts=[
            {
                "id": str(memory.id),
                "type": memory.type,
                "topic": fact_topic(memory),
                "text": memory.text,
            }
            for memory in existing
        ],
        prompt_areas=[
            {"topic": area.key, "title": area.title, "summary": area.summary} for area in areas
        ],
        edited_at=user.memory_edited_at,
        active_facts=tuple(
            FactView(
                text=memory.text,
                confirmed_at=memory.last_confirmed_at,
            )
            for memory in existing
        ),
    )


def writes_from_ops(
    result_ops: list,
    *,
    chat_id: UUID | None,
    explicit_remember: bool,
    include_sensitive: bool,
    min_confidence: float,
    transcript: str,
    existing_texts: Iterable[str] = (),
) -> tuple[list[MemoryFactWrite], int]:
    writes: list[MemoryFactWrite] = []
    skipped = 0
    for op in result_ops:
        confidence = float(op.confidence)
        if confidence < min_confidence:
            skipped += 1
            continue
        text = normalize_memory_text(op.text or "")
        sensitivity = op.sensitivity or classify_memory_sensitivity(text)
        if should_skip_sensitive_persist(
            sensitivity=sensitivity,
            text=text or op.match_text or "",
            explicit_remember=explicit_remember,
            include_sensitive=include_sensitive,
        ) and op.op in {"add", "update", "supersede"}:
            logger.info(
                "Skipping sensitive memory persist op=%s sensitivity=%s",
                op.op,
                sensitivity,
            )
            skipped += 1
            continue
        # A delete or mute names an existing fact by match_text; it writes no text.
        writes_text = op.op not in _MATCH_ONLY_OPS
        if writes_text and not text:
            skipped += 1
            continue
        if writes_text and is_unclaimed_user_name(text, transcript, existing_texts=existing_texts):
            logger.info("Skipping memory name the user did not claim")
            skipped += 1
            continue
        if writes_text and is_one_off_schedule_fact(text):
            logger.info("Skipping one-off reminder stored as memory")
            skipped += 1
            continue
        # No valid topic keeps a matched fact where it is; a new fact then gets
        # the default document for its type.
        topic = parse_topic(op.topic)
        writes.append(
            MemoryFactWrite(
                op=op.op,
                # The document decides the type, so the two never disagree.
                type=topic_memory_type(topic) if topic else op.type,
                text=text,
                confidence=confidence,
                sensitivity=sensitivity,
                # What the user asked to keep is never pushed out by the fact cap.
                importance=EXPLICIT_IMPORTANCE
                if explicit_remember and writes_text
                else min(float(op.importance), MODEL_IMPORTANCE_MAX),
                match_text=op.match_text,
                source_chat_id=chat_id,
                topic=topic,
                area_title=op.topic_title if topic and is_area(topic) else None,
                area_summary=op.topic_summary if topic and is_area(topic) else None,
            )
        )
    return writes, skipped


def named_forget_deletes(
    transcript: str,
    *,
    existing_facts: dict[UUID, str],
    chat_id: UUID | None,
) -> list[MemoryFactWrite]:
    """Delete stored facts the user named when the model returned no delete."""
    return _named_fact_ops("delete", forget_requests(transcript), existing_facts, chat_id)


def named_mute_ops(
    transcript: str,
    *,
    existing_facts: dict[UUID, str],
    chat_id: UUID | None,
) -> list[MemoryFactWrite]:
    """Mute stored facts the user named ("stop mentioning my job") when the model did not."""
    return _named_fact_ops("mute", mute_requests(transcript), existing_facts, chat_id)


def _named_fact_ops(
    op: str,
    phrases: list[str],
    existing_facts: dict[UUID, str],
    chat_id: UUID | None,
) -> list[MemoryFactWrite]:
    return [
        MemoryFactWrite(
            op=op,
            type="fact",
            text="",
            confidence=1.0,
            match_text=fact_text,
            source_chat_id=chat_id,
        )
        for fact_text in existing_facts.values()
        if any(phrase_names_fact(phrase, fact_text) for phrase in phrases)
    ]


def without_reset_requests(transcript: str) -> str:
    """Drop "forget everything you know about me" lines: a card the user taps does that."""
    lines = [
        line
        for line in transcript.splitlines()
        if memory_reset_request(line.removeprefix("User:").strip()) is None
    ]
    return "\n".join(lines).strip()


async def extract_and_store_memories(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> ExtractOutcome:
    """Learn from a chat's unread user lines (``transcript`` is the fallback)."""
    return await _extract_pass(
        settings, user_id=user_id, chat_id=chat_id, transcript=transcript, from_history=False
    )


async def extract_history_chat(
    settings: Settings, *, user_id: UUID, chat_id: UUID
) -> ExtractOutcome:
    """Learn from one past chat's recent user lines, for the history scan.

    Old lines only fill gaps: saved facts may be newer, so none is changed or
    removed. Lines from before the user's last hand edit are not read, so the
    pass cannot bring back what they removed. The chat's live cursor and retry
    count are left alone.
    """
    return await _extract_pass(
        settings, user_id=user_id, chat_id=chat_id, transcript="", from_history=True
    )


async def _extract_pass(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
    from_history: bool,
) -> ExtractOutcome:
    try:
        lock_token = await acquire_memory_write_lock(user_id)
        if not lock_token:
            logger.info(
                "Memory extraction skipped: write lock held for user_id=%s",
                user_id,
            )
            return "skipped_lock"
        try:
            async with SessionLocal() as session:
                snapshot = await load_memory_snapshot(session, user_id)
                if not snapshot.memory_enabled:
                    return None
                if from_history:
                    # Read under the write lock, so a hand edit cannot land
                    # between this cut-off and the writes below.
                    expanded = await history_chat_transcript(
                        session, chat_id, newer_than=snapshot.edited_at
                    )
                    newest_cursor = None
                else:
                    expanded, newest_cursor = await expand_memory_extract_transcript(
                        session,
                        user_id=user_id,
                        chat_id=chat_id,
                        fallback_transcript=transcript,
                    )
            expanded = without_reset_requests(expanded)
            if not expanded.strip():
                if newest_cursor:
                    await stamp_extract_cursor(user_id, chat_id, newest_cursor)
                return None

            forget = is_explicit_forget_command(expanded)
            mute = is_explicit_mute_command(expanded)
            # A correction changes a saved fact by the user's word, like a hand edit.
            correction = is_memory_correction(expanded)
            explicit_remember = is_explicit_memory_command(expanded) and not forget
            if not explicit_remember and not forget and not is_memory_candidate(expanded):
                # Small talk only: nothing to learn, but the lines are read. Moving
                # the cursor keeps a run of "ok"s from hiding every later line.
                if newest_cursor:
                    await stamp_extract_cursor(user_id, chat_id, newest_cursor)
                logger.info(
                    "memory_extract_yield user_id=%s applied=0 skipped=candidate",
                    user_id,
                )
                return None

            result = await memory_llm.revise_memory_facts(
                settings,
                expanded,
                existing_facts=snapshot.prompt_facts,
                existing_areas=snapshot.prompt_areas,
                from_history=from_history,
            )
            outcome: ExtractOutcome = None
            if result is None:
                # Provider error, timeout or unreadable JSON. Keep the cursor so the
                # next turn retries these lines, up to FAILED_PASS_LIMIT times.
                outcome = "model_failed"
                advance_cursor = (
                    False if from_history else await note_failed_extract_pass(user_id, chat_id)
                )
                logger.warning(
                    "memory_extract_model_failed user_id=%s chat_id=%s moving_on=%s",
                    user_id,
                    chat_id,
                    advance_cursor,
                )
            else:
                advance_cursor = True
                if not from_history:
                    await clear_failed_extract_passes(user_id, chat_id)
            writes, skipped = writes_from_ops(
                result.ops if result else [],
                chat_id=chat_id,
                explicit_remember=explicit_remember,
                include_sensitive=snapshot.include_sensitive,
                min_confidence=settings.memory_min_confidence,
                transcript=expanded,
                existing_texts=snapshot.existing_facts.values(),
            )
            if forget and not from_history and not any(write.op == "delete" for write in writes):
                writes.extend(
                    named_forget_deletes(
                        expanded,
                        existing_facts=snapshot.existing_facts,
                        chat_id=chat_id,
                    )
                )
            if mute and not from_history and not any(write.op == "mute" for write in writes):
                writes.extend(
                    named_mute_ops(
                        expanded,
                        existing_facts=snapshot.existing_facts,
                        chat_id=chat_id,
                    )
                )
            if not forget:
                writes.extend(
                    stated_fact_writes(
                        expanded,
                        chat_id=chat_id,
                        existing_facts=(
                            (str(fact["type"]), str(fact["text"])) for fact in snapshot.prompt_facts
                        ),
                        already=writes,
                        include_sensitive=snapshot.include_sensitive,
                        explicit_remember=explicit_remember,
                        model_ops=result.ops if result else (),
                    )
                )
            if from_history:
                writes = [write for write in writes if write.op == "add"]
            else:
                already = {
                    normalize_memory_text(write.match_text or "")
                    for write in writes
                    if write.op == "delete"
                }
                fresh = {
                    normalize_memory_text(write.text)
                    for write in writes
                    if write.op != "delete" and write.text
                }
                for text in texts_to_drop(snapshot.active_facts):
                    key = normalize_memory_text(text)
                    if key in already or key in fresh:
                        continue
                    already.add(key)
                    writes.append(
                        MemoryFactWrite(
                            op="delete",
                            type="fact",
                            text="",
                            confidence=1.0,
                            match_text=text,
                        )
                    )
            if not writes:
                if newest_cursor and advance_cursor:
                    await stamp_extract_cursor(user_id, chat_id, newest_cursor)
                logger.info("memory_extract_yield user_id=%s applied=0 skipped=empty", user_id)
                return outcome
            await apply_memory_facts(
                settings,
                user_id=user_id,
                writes=writes,
                session_factory=SessionLocal,
                memories=memories_repo,
                # A history add that matches a saved fact leaves it as it is.
                expected_facts={} if from_history else snapshot.existing_facts,
                manual_edit=(forget or mute or correction) and not from_history,
            )
            logger.info(
                "memory_extract_yield user_id=%s applied=%s skipped=%s",
                user_id,
                len(writes),
                skipped,
            )
            if newest_cursor and advance_cursor:
                await stamp_extract_cursor(user_id, chat_id, newest_cursor)
        finally:
            await release_memory_write_lock(user_id, lock_token)
        return outcome
    except Exception:
        logger.exception("Memory extraction failed for user_id=%s", user_id)
        raise
