"""Memory, recent-window, and history-gap reads for one chat prompt."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import Chat, User
from app.modules import memory as memory_service
from app.modules import todos as todos_service
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.services.chat.prompt_constants import is_broad_self_question
from app.services.context_window import (
    UNSUMMARIZED_GAP_MAX_MESSAGES,
    messages_within_token_budget,
    unsummarized_gap_bounds,
)

_SLIM_MEMORY_MAX_CHARS = 1000
_BROAD_SELF_HISTORY_QUERY = (
    "Personal details the user stated about their background, work, employer, interests, "
    "preferences, communication style, goals, and active projects"
)


def _cap_slim_memory_block(block: str) -> str:
    if len(block) <= _SLIM_MEMORY_MAX_CHARS:
        return block

    lines = block.splitlines()
    if not lines:
        return ""

    # Memory blocks are rendered as a title followed by section headings and
    # bullet facts. Keep complete facts and skip any one fact that does not fit;
    # slicing the string can turn a remembered detail into a different claim.
    packed = [lines[0]]
    current_heading: str | None = None
    emitted_heading: str | None = None
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            current_heading = stripped
            continue
        if not stripped.startswith("- "):
            continue

        addition: list[str] = []
        if current_heading and current_heading != emitted_heading:
            addition.extend(["", current_heading])
        addition.append(stripped)
        trial = "\n".join([*packed, *addition])
        if len(trial) > _SLIM_MEMORY_MAX_CHARS:
            continue
        packed.extend(addition)
        emitted_heading = current_heading

    return "\n".join(packed) if len(packed) > 1 else ""


@dataclass
class _PromptContextBlocks:
    memory_block: str
    todos_section: str | None
    gmail_todos_section: str | None
    recent_all: list[Any]
    attachment_rag_block: str
    chat: Chat | None
    history_rag_query_vec: list[float] | None = None


async def _load_context_blocks(
    user: User,
    chat_id: UUID,
    settings: Settings,
    *,
    chat: Chat | None,
    query_text: str | None,
    recent_limit: int,
    slim_context: bool,
    client_timezone: str | None,
    out: dict[str, object] | None,
    load_memory: bool = False,
    history_rag: bool = False,
    recent_messages: list[Any] | None = None,
) -> _PromptContextBlocks:
    """Load memory/todos/RAG + recent messages for the system prompt.

    Each gather branch opens a short-lived session so external HTTP (RAG/memory
    embed) cannot pin a caller's connection across the concurrent load.
    Chat-history query embed overlaps the gather; recent-window excludes are
    applied later when hits are filtered.
    """

    async def _history_rag_embed() -> list[float] | None:
        if not history_rag or not query_text or not query_text.strip():
            return None
        from app.services.chat import history_rag as chat_history_rag_service

        history_query = (
            _BROAD_SELF_HISTORY_QUERY if is_broad_self_question(query_text) else query_text
        )
        return await chat_history_rag_service.embed_query_for_prompt(
            settings, user_id=user.id, query=history_query
        )

    async def _fetch_recent() -> list[Any]:
        if recent_messages is not None:
            return recent_messages
        async with SessionLocal() as s:
            return await messages_repo.list_recent(s, chat_id, limit=recent_limit)

    if slim_context and not load_memory:
        if history_rag:
            recent_all, history_rag_query_vec = await asyncio.gather(
                _fetch_recent(),
                _history_rag_embed(),
            )
        else:
            recent_all = await _fetch_recent()
            history_rag_query_vec = None
        if out is not None:
            out["recalled"] = 0
            out["memory_hints"] = []
        return _PromptContextBlocks(
            memory_block="",
            todos_section=None,
            gmail_todos_section=None,
            recent_all=recent_all,
            attachment_rag_block="",
            chat=chat,
            history_rag_query_vec=history_rag_query_vec,
        )

    # Each of these is an independent read with no dependency on the others'
    # output — give each its own short-lived session (a single AsyncSession
    # cannot safely run concurrent operations) and gather them, instead of
    # awaiting four DB round-trips back-to-back before the LLM call starts.
    # Cap concurrent DB checkouts so one turn cannot saturate the pool.
    db_slots = asyncio.Semaphore(max(1, settings.context_db_concurrency))

    async def _memory_block() -> str:
        async with db_slots, SessionLocal() as s:
            return await memory_service.get_memory_block(
                s,
                user,
                settings,
                query_text=query_text,
                exclude_sensitive=memory_service.exclude_sensitive_for_query(query_text),
            )

    if slim_context and load_memory:
        recent_all, memory_block, history_rag_query_vec = await asyncio.gather(
            _fetch_recent(),
            _memory_block(),
            _history_rag_embed(),
        )
        if out is not None:
            out["recalled"] = 0
            out["memory_hints"] = []
        return _PromptContextBlocks(
            memory_block=_cap_slim_memory_block(memory_block),
            todos_section=None,
            gmail_todos_section=None,
            recent_all=recent_all,
            attachment_rag_block="",
            chat=chat,
            history_rag_query_vec=history_rag_query_vec,
        )

    if chat is None:
        async with SessionLocal() as s:
            chat = await chats_repo.get_by_id(s, chat_id, user.id)

    async def _todos_section() -> tuple[str | None, str | None]:
        async with db_slots, SessionLocal() as s:
            loaded = await todos_service.build_todos_system_section(
                s,
                user,
                settings,
                client_timezone=client_timezone,
                query_text=query_text,
            )
        if loaded is None:
            return None, None
        if isinstance(loaded, todos_service.TodosPromptSections):
            return loaded.own, loaded.gmail
        if isinstance(loaded, str):
            return loaded, None
        return None, None

    async def _attachment_rag_block() -> str:
        # HTTP/embed-bound — do not hold a DB pool slot.
        if not settings.attachment_rag_enabled or not query_text:
            return ""
        from app.modules.attachments import rag as attachment_rag_service

        return await attachment_rag_service.retrieve_for_prompt(
            settings,
            user_id=user.id,
            chat_id=chat_id,
            query=query_text,
        )

    async def _load_recent() -> list[Any]:
        if recent_messages is not None:
            return recent_messages
        # Own session so the caller's connection is not pinned across the gather
        # (RAG embed / memory embed can take seconds).
        async with db_slots, SessionLocal() as s:
            return await messages_repo.list_recent(s, chat_id, limit=recent_limit)

    (
        memory_block,
        todos_payload,
        recent_all,
        attachment_rag_block,
        history_rag_query_vec,
    ) = await asyncio.gather(
        _memory_block(),
        _todos_section(),
        _load_recent(),
        _attachment_rag_block(),
        _history_rag_embed(),
    )
    todos_section, gmail_todos_section = todos_payload
    if out is not None:
        labels = set(memory_service.SECTION_LABELS.values())
        hints = [
            line[3:].strip()
            for line in memory_block.split("\n")
            if line.startswith("## ") and line[3:].strip() in labels
        ]
        out["recalled"] = len(hints)
        out["memory_hints"] = hints[:3]
    return _PromptContextBlocks(
        memory_block=memory_block,
        todos_section=todos_section,
        gmail_todos_section=gmail_todos_section,
        recent_all=recent_all,
        attachment_rag_block=attachment_rag_block,
        chat=chat,
        history_rag_query_vec=history_rag_query_vec,
    )


def _persisted_messages(window: list[Any], current_user_message_id: UUID | None) -> list[Any]:
    """Drop the synthetic current turn. It is not a stored row yet."""
    if current_user_message_id is None:
        return window
    return [
        message for message in window if getattr(message, "id", None) != current_user_message_id
    ]


async def _load_unsummarized_gap(
    chat_id: UUID,
    chat: Chat | None,
    window: list[Any],
    tail: list[Any],
    *,
    recent_limit: int,
    token_budget: int,
    current_user_message_id: UUID | None,
) -> list[Any]:
    """Messages after the summary and before the messages the prompt kept.

    ``tail`` is that kept list. A synthetic current user row can push one
    stored message out of a full window; that row is included here, then the
    whole gap is cut to the tokens the recent window did not already use.
    """
    tail_ids = {message.id for message in tail}
    dropped = [
        message
        for message in _persisted_messages(window, current_user_message_id)
        if message.id not in tail_ids
    ]
    older: list[Any] = []
    persisted = _persisted_messages(window, current_user_message_id)
    if chat is not None and len(persisted) >= recent_limit and persisted:
        oldest = persisted[0]
        created_at = getattr(oldest, "created_at", None)
        oldest_id = getattr(oldest, "id", None)
        if created_at is not None and oldest_id is not None:
            summarized = int(getattr(chat, "summary_message_count", 0) or 0)
            async with SessionLocal() as session:
                total = await messages_repo.count_for_chat(session, chat_id)
                bounds = unsummarized_gap_bounds(
                    total=total,
                    summarized=summarized,
                    loaded=len(persisted),
                )
                if bounds is not None:
                    _offset, count = bounds
                    older = await messages_repo.list_before(
                        session,
                        chat_id,
                        before_created_at=created_at,
                        before_id=oldest_id,
                        limit=count,
                    )
    return messages_within_token_budget(
        [*older, *dropped],
        token_budget,
        max_messages=UNSUMMARIZED_GAP_MAX_MESSAGES,
    )
