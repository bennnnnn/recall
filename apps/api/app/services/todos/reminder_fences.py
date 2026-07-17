"""Materialize ```reminder JSON fences from assistant replies."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem
from app.repositories import todos as todos_repo
from app.services import home as home_service
from app.services import time_context as time_context_service
from app.services.todos.actions import _ACTION_RELOAD_LIMIT, REMINDER_TOPIC

logger = logging.getLogger(__name__)

_REMINDER_FENCE = re.compile(r"```reminder\s*\n([\s\S]*?)```", re.IGNORECASE)


class _ReminderFence(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    due_at: datetime


@dataclass
class _ReminderFenceCreateState:
    session: AsyncSession
    user_id: UUID
    chat_id: UUID
    user_timezone: str | None
    existing: list[TodoItem] = field(default_factory=list)
    existing_loaded: bool = False
    created: int = 0


async def _load_existing(state: _ReminderFenceCreateState) -> None:
    """Load open reminders once (lazily) so multi-fence replies don't re-read the DB."""
    if not state.existing_loaded:
        state.existing = await todos_repo.list_for_user(
            state.session, state.user_id, limit=_ACTION_RELOAD_LIMIT
        )
        state.existing_loaded = True


async def _create_one(state: _ReminderFenceCreateState, raw: str) -> bool:
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        logger.warning("Invalid reminder fence JSON for user_id=%s", state.user_id)
        return False
    if not isinstance(data, dict):
        return False
    try:
        draft = _ReminderFence.model_validate(data)
    except ValidationError:
        logger.warning("Invalid reminder fence payload for user_id=%s", state.user_id)
        return False
    due_at = time_context_service.normalize_due_at(draft.due_at, state.user_timezone)
    if due_at is None:
        return False
    title = draft.title.strip()
    await _load_existing(state)
    if any(
        (i.content or "").strip().lower() == title.lower()
        and i.due_at is not None
        and not i.checked
        for i in state.existing
    ):
        return True  # already present — still strip fence
    new_todo = await todos_repo.create(
        state.session,
        user_id=state.user_id,
        content=title,
        topic=REMINDER_TOPIC,
        chat_id=state.chat_id,
        due_at=due_at,
    )
    state.existing.append(new_todo)
    state.created += 1
    logger.info(
        "Reminder fence applied: user_id=%s chat_id=%s title=%s",
        state.user_id,
        state.chat_id,
        title[:80],
    )
    return True


async def materialize_reminder_fences(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    assistant_text: str,
    user_timezone: str | None,
) -> tuple[str, int]:
    """Create reminders from ```reminder JSON fences and strip fences from the reply.

    Returns (updated_text, created_count). The chat model must emit the fence for a
    dated reminder to be saved — prose alone is not enough.
    """
    if not _REMINDER_FENCE.search(assistant_text):
        return assistant_text, 0

    # Load open reminders once (lazily, on the first VALID fence) instead of
    # per fence — a reply with several ```reminder fences used to re-read up
    # to 500 rows (and commit) for each. Lazy so an all-invalid reply (the
    # common error case) still touches the DB zero times, matching prior
    # behavior. We mutate this list as we create so duplicate fences in the
    # same reply are still deduped in-memory.
    state = _ReminderFenceCreateState(
        session=session,
        user_id=user_id,
        chat_id=chat_id,
        user_timezone=user_timezone,
    )

    # Process fences sequentially (create commits per row).
    parts: list[str] = []
    last = 0
    for match in _REMINDER_FENCE.finditer(assistant_text):
        parts.append(assistant_text[last : match.start()])
        ok = await _create_one(state, match.group(1))
        if not ok:
            parts.append(match.group(0))  # keep invalid fence visible for debugging
        last = match.end()
    parts.append(assistant_text[last:])
    updated = "".join(parts)
    updated = re.sub(r"\n{3,}", "\n\n", updated).strip()
    if state.created:
        await home_service.invalidate_home_cache(user_id)
    return updated, state.created
