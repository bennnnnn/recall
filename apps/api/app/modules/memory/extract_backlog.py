"""Unprocessed user lines for a memory extraction pass.

Each job must see every user message since the previous successful pass, not
only the current turn. Redis stores a per-chat cursor; the payload transcript
is the fallback when Redis or Neon is unavailable.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.modules.conversation import history as chat_history
from app.modules.memory.grounding import SourceLine
from app.modules.memory.text import memory_extract_user_text
from app.services.text_normalize import cap_text_head_tail

if TYPE_CHECKING:
    from app.models.orm import Message

logger = logging.getLogger(__name__)

_MEMORY_TRANSCRIPT_MAX_CHARS = 4000
_MEMORY_EXTRACT_BACKLOG = 20
# The chat before the unread lines, read as context: what a short line answers, and
# whether the lines go on with a story (a story's start is often a dozen lines back).
# Each message is cut: the user's lines to the first number, replies to the second, and
# the last reply, whose question a short line may answer, to the third.
_CONTEXT_MESSAGES = 16
_CONTEXT_USER_CHARS = 300
_CONTEXT_REPLY_CHARS = 160
_CONTEXT_LAST_REPLY_CHARS = 400
_CURSOR_TTL_SECONDS = 60 * 60 * 24 * 60
# A failed model pass keeps the cursor so the next turn retries the same lines.
# After this many failures in a row the lines are skipped, so one line the model
# always fails on cannot hold back every later line in the chat.
FAILED_PASS_LIMIT = 3
_FAILED_PASS_TTL_SECONDS = 60 * 60 * 24


@dataclass(frozen=True)
class PassLines:
    """The user lines one pass reads: the model's transcript and the lines with their
    messages; ``cursor`` is where a live pass moves once they are read."""

    transcript: str
    sources: tuple[SourceLine, ...] = ()
    cursor: str | None = None
    # The messages just before these lines, oldest first, as (role, text): context,
    # never a source of facts.
    context: tuple[tuple[str, str], ...] = ()


def _cursor_key(user_id: UUID, chat_id: UUID) -> str:
    return f"memory:extract_cursor:{user_id}:{chat_id}"


def _failed_pass_key(user_id: UUID, chat_id: UUID) -> str:
    return f"memory:extract_failures:{user_id}:{chat_id}"


def parse_extract_cursor(raw: str | None) -> tuple[datetime | None, UUID | None]:
    if not raw:
        return None, None
    stamp, sep, id_part = raw.partition("|")
    if not sep or not id_part:
        return None, None
    try:
        return datetime.fromisoformat(stamp), UUID(id_part)
    except ValueError:
        return None, None


def format_extract_cursor(created_at: datetime, message_id: UUID) -> str:
    return f"{created_at.isoformat()}|{message_id}"


def _readable_lines(user_texts: Iterable[str]) -> list[str]:
    """The user's lines a pass reads. One that only says when ("6pm", "tomorrow at 6")
    answers a reminder's or a plan's question and says nothing about them: read alone,
    "6pm" became "User works or starts their day at 18:00" (2026-11-06)."""
    from app.modules import todos

    lines: list[str] = []
    for raw in user_texts:
        cleaned = memory_extract_user_text(raw)
        if cleaned and not todos.is_only_a_when(cleaned):
            lines.append(cleaned)
    return lines


def format_user_memory_transcript(user_texts: list[str]) -> str:
    """The user's lines for the model, one ``User:`` line each."""
    return "\n".join(f"User: {line}" for line in _readable_lines(user_texts))


def source_lines(rows: Iterable[tuple[UUID | None, str]]) -> tuple[SourceLine, ...]:
    """The lines a pass read with the message each came from: what a fact's quote is
    checked against, and where the fact's "From" link points (``grounding``)."""
    return tuple(
        SourceLine(text=line, message_id=message_id)
        for message_id, raw in rows
        for line in _readable_lines([raw])
    )


def format_context(messages: Sequence[tuple[str, str]]) -> str:
    """The chat before the unread lines for the prompt: ``User:`` / ``Assistant:`` lines,
    each cut (a reply's question is usually at its end, so head and tail are kept)."""
    last_reply = max(
        (index for index, (role, _) in enumerate(messages) if role == "assistant"), default=-1
    )
    lines: list[str] = []
    for index, (role, raw) in enumerate(messages):
        if role not in ("user", "assistant"):
            continue
        room = (
            _CONTEXT_USER_CHARS
            if role == "user"
            else _CONTEXT_LAST_REPLY_CHARS
            if index == last_reply
            else _CONTEXT_REPLY_CHARS
        )
        text = " ".join(cap_text_head_tail(memory_extract_user_text(raw), room).split())
        if text:
            lines.append(f"{role.capitalize()}: {text}")
    return "\n".join(lines)


async def history_chat_transcript(
    session: AsyncSession,
    chat_id: UUID,
    *,
    newer_than: datetime | None,
) -> PassLines:
    """A past chat's most recent user lines, capped like a live pass.

    Lines written at or before ``newer_than`` (the user's last hand edit to
    memory) are left out, so reading them cannot undo that edit.
    """
    rows = await chat_history.user_lines_since(
        session, chat_id, newer_than=newer_than, limit=_MEMORY_EXTRACT_BACKLOG
    )
    return PassLines(
        transcript=cap_text_head_tail(
            format_user_memory_transcript([row.content for row in rows]),
            _MEMORY_TRANSCRIPT_MAX_CHARS,
        ),
        sources=source_lines((row.id, row.content) for row in rows),
    )


async def expand_memory_extract_transcript(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    fallback_transcript: str,
) -> PassLines:
    """The unread lines, and the cursor the caller stamps once the model pass succeeds.

    The fallback transcript (Redis or Neon down) has no messages to point at.
    """
    after_created_at, after_id = await _read_cursor(user_id, chat_id)
    try:
        rows = await chat_history.user_lines_since(
            session,
            chat_id,
            after_created_at=after_created_at,
            after_id=after_id,
            limit=_MEMORY_EXTRACT_BACKLOG,
        )
    except Exception:
        logger.debug("memory extract backlog list failed chat_id=%s", chat_id, exc_info=True)
        return _fallback_lines(fallback_transcript)

    # Lines read and all left out (only a when) teach nothing; no lines at all fall back.
    if not rows:
        return _fallback_lines(fallback_transcript)
    last = rows[-1]
    return PassLines(
        context=await _chat_before(session, chat_id, rows[0]),
        transcript=cap_text_head_tail(
            format_user_memory_transcript([row.content for row in rows]),
            _MEMORY_TRANSCRIPT_MAX_CHARS,
        ),
        sources=source_lines((row.id, row.content) for row in rows),
        cursor=format_extract_cursor(last.created_at, last.id),
    )


async def _chat_before(
    session: AsyncSession, chat_id: UUID, first_unread: Message
) -> tuple[tuple[str, str], ...]:
    """The messages just before the unread lines. Earlier passes read them; they say what
    "forget that" or a one-word answer points at, and whether the lines go on with a story.
    """
    try:
        earlier = await chat_history.messages_before(
            session, chat_id, first_unread, limit=_CONTEXT_MESSAGES
        )
    except Exception:
        logger.debug("memory extract context read failed chat_id=%s", chat_id, exc_info=True)
        return ()
    return tuple((message.role, message.content) for message in earlier)


def _fallback_lines(transcript: str) -> PassLines:
    """The job payload's transcript: its ``User:`` lines are what a quote is held to."""
    said: list[str] = []
    speaker = "user"
    # A line without a label goes on the speaker before it (a message of several lines);
    # a transcript with no labels at all is the user's own words.
    for line in transcript.splitlines():
        role, colon, rest = line.partition(":")
        if colon and role.strip().casefold() in ("user", "assistant"):
            speaker, line = role.strip().casefold(), rest
        if speaker == "user" and line.strip():
            said.append(line.strip())
    return PassLines(
        transcript=cap_text_head_tail(transcript, _MEMORY_TRANSCRIPT_MAX_CHARS),
        sources=source_lines((None, line) for line in said),
    )


async def _read_cursor(user_id: UUID, chat_id: UUID) -> tuple[datetime | None, UUID | None]:
    try:
        raw = await get_redis_client().get(_cursor_key(user_id, chat_id))
        if isinstance(raw, bytes):
            raw = raw.decode()
        return parse_extract_cursor(raw if isinstance(raw, str) else None)
    except Exception:
        logger.debug("memory extract cursor read failed chat_id=%s", chat_id, exc_info=True)
        return None, None


async def stamp_extract_cursor(user_id: UUID, chat_id: UUID, cursor: str) -> None:
    try:
        await get_redis_client().set(
            _cursor_key(user_id, chat_id),
            cursor,
            ex=_CURSOR_TTL_SECONDS,
        )
    except Exception:
        logger.debug("memory extract cursor write failed chat_id=%s", chat_id, exc_info=True)


async def note_failed_extract_pass(user_id: UUID, chat_id: UUID) -> bool:
    """Count a model failure for this chat. True when its lines should be skipped."""
    key = _failed_pass_key(user_id, chat_id)
    try:
        redis = get_redis_client()
        # One transaction: a crash between the two left a count that never expired.
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, _FAILED_PASS_TTL_SECONDS)
            failures = int((await pipe.execute())[0])
        if failures < FAILED_PASS_LIMIT:
            return False
        await redis.delete(key)
    except Exception:
        # Without Redis the cursor cannot be kept either, so nothing is held back.
        logger.debug("memory extract failure count failed chat_id=%s", chat_id, exc_info=True)
    return True


async def clear_failed_extract_passes(user_id: UUID, chat_id: UUID) -> None:
    try:
        await get_redis_client().delete(_failed_pass_key(user_id, chat_id))
    except Exception:
        logger.debug("memory extract failure reset failed chat_id=%s", chat_id, exc_info=True)
