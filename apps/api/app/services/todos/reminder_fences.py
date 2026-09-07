"""Materialize ```reminder JSON fences from assistant replies."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal, Self
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem
from app.models.schemas import TodoActionItem
from app.models.schemas.schedule import RecurrenceRule
from app.repositories import todos as todos_repo
from app.services import home as home_service
from app.services import time_context as time_context_service
from app.services.todos.actions import (
    _ACTION_RELOAD_LIMIT,
    MAX_TODO_ACTIONS_PER_TURN,
    REMINDER_TOPIC,
    apply_todo_actions,
)
from app.services.todos.recurrence import snap_first_due

logger = logging.getLogger(__name__)

_REMINDER_FENCE = re.compile(r"```reminder\s*\n([\s\S]*?)```", re.IGNORECASE)
_INVALID_FENCE = "*Could not set that reminder — the format was invalid.*"
_USER_REMIND = re.compile(
    r"remind\s+me\s+(?:to\s+)?(?P<title>.+?)\s+"
    r"(?P<day>today|tomorrow)\s+at\s+"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*"
    r"(?P<ampm>a\.?m\.?|p\.?m\.?)",
    re.IGNORECASE,
)
_FAIL_VERB = {
    "add": "set",
    "delete": "delete",
    "complete": "complete",
    "uncheck": "reopen",
    "set_due": "reschedule",
}
_OK_PREFIX = {
    "add": "Set",
    "delete": "Deleted",
    "complete": "Done",
    "uncheck": "Reopened",
    "set_due": "Moved",
}


class _ReminderFence(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    action: Literal["add", "complete", "uncheck", "delete", "set_due"] = "add"
    title: str = Field(
        min_length=1,
        max_length=500,
        validation_alias=AliasChoices("title", "content", "task", "name"),
    )
    due_at: datetime | None = None
    repeat: RecurrenceRule | None = Field(default=None, alias="recurrence_rule")

    @field_validator("due_at", mode="before")
    @classmethod
    def _coerce_due_at(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith(("Z", "z")):
            raw = raw[:-1] + "+00:00"
        if "T" not in raw and " " in raw[:19]:
            raw = raw.replace(" ", "T", 1)
        date_only = len(raw) == 10 and raw[4] == "-" and raw[7] == "-"
        if date_only:
            raise ValueError("due_at must include a time")
        return raw

    @model_validator(mode="after")
    def due_required_for_add_and_set(self) -> Self:
        if self.action in ("add", "set_due") and self.due_at is None:
            raise ValueError("due_at is required")
        return self


@dataclass
class _ReminderFenceCreateState:
    session: AsyncSession
    user_id: UUID
    chat_id: UUID
    user_timezone: str | None
    existing: list[TodoItem] = field(default_factory=list)
    existing_loaded: bool = False
    applied: int = 0


def format_schedule_when(
    due_at: datetime,
    user_timezone: str | None,
    repeat: RecurrenceRule | str | None = None,
) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    due_local = (
        due_at.astimezone(tz) if due_at.tzinfo else due_at.replace(tzinfo=UTC).astimezone(tz)
    )
    hour = due_local.strftime("%I").lstrip("0") or "0"
    when = (
        f"{due_local.strftime('%A')}, {due_local.strftime('%b')} {due_local.day}, "
        f"{hour}:{due_local.strftime('%M')} {due_local.strftime('%p')}"
    )
    if repeat:
        when = f"{when} · {repeat}"
    return when


def format_schedule_result(
    *,
    action: str,
    title: str,
    due_at: datetime | None,
    repeat: RecurrenceRule | str | None,
    user_timezone: str | None,
    ok: bool,
) -> str:
    if not ok:
        verb = _FAIL_VERB.get(action, "update")
        return f"Could not {verb} {title}."
    prefix = _OK_PREFIX.get(action, "Set")
    if action in ("add", "set_due") and due_at is not None:
        return f"{prefix}: {title} — {format_schedule_when(due_at, user_timezone, repeat)}."
    return f"{prefix}: {title}."


def _load_fence_json(raw: str) -> dict[str, object] | None:
    text = raw.strip()
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        snippet = text[start : end + 1]
        if snippet != text:
            candidates.append(snippet)
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _parse_fence(raw: str) -> _ReminderFence | None:
    data = _load_fence_json(raw)
    if data is None:
        return None
    try:
        return _ReminderFence.model_validate(data)
    except ValidationError:
        return None


def _explicit_user_remind(
    user_text: str | None, user_timezone: str | None
) -> _ReminderFence | None:
    """Parse 'remind me … today/tomorrow at 6pm' from the user — never invent a clock."""
    if not user_text:
        return None
    match = _USER_REMIND.search(user_text)
    if match is None:
        return None
    title = match.group("title").strip().strip("\"'").rstrip(".,;:")
    if not title:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    ampm = match.group("ampm").lower().replace(".", "")
    if hour == 12:
        hour = 0 if ampm.startswith("a") else 12
    elif ampm.startswith("p"):
        hour += 12
    if hour > 23 or minute > 59:
        return None
    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    day = now.date()
    if match.group("day").lower() == "tomorrow":
        day = day + timedelta(days=1)
    due = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
    return _ReminderFence(action="add", title=title[:500], due_at=due)


async def _load_existing(state: _ReminderFenceCreateState) -> None:
    """Load open reminders once (lazily) so multi-fence replies don't re-read the DB."""
    if not state.existing_loaded:
        state.existing = await todos_repo.list_for_user(
            state.session, state.user_id, limit=_ACTION_RELOAD_LIMIT
        )
        state.existing_loaded = True


def _existing_open_match(state: _ReminderFenceCreateState, title: str) -> TodoItem | None:
    needle = title.lower()
    for item in state.existing:
        if (item.content or "").strip().lower() != needle:
            continue
        if item.due_at is None or item.checked:
            continue
        return item
    return None


async def _create_one(state: _ReminderFenceCreateState, draft: _ReminderFence) -> tuple[str, bool]:
    due_at = time_context_service.normalize_due_at(draft.due_at, state.user_timezone)
    if due_at is None:
        return format_schedule_result(
            action="add",
            title=draft.title.strip(),
            due_at=None,
            repeat=draft.repeat,
            user_timezone=state.user_timezone,
            ok=False,
        ), False
    if draft.repeat:
        due_at = snap_first_due(due_at, draft.repeat, timezone=state.user_timezone)
    title = draft.title.strip()
    await _load_existing(state)
    match = _existing_open_match(state, title)
    if match is not None:
        saved_due = match.due_at if match.due_at is not None else due_at
        return format_schedule_result(
            action="add",
            title=title,
            due_at=saved_due,
            repeat=getattr(match, "recurrence_rule", None) or draft.repeat,
            user_timezone=state.user_timezone,
            ok=True,
        ), True
    new_todo = await todos_repo.create(
        state.session,
        user_id=state.user_id,
        content=title,
        topic=REMINDER_TOPIC,
        chat_id=state.chat_id,
        due_at=due_at,
        recurrence_rule=draft.repeat,
    )
    state.existing.append(new_todo)
    logger.info(
        "Reminder fence applied: user_id=%s chat_id=%s title=%s",
        state.user_id,
        state.chat_id,
        title[:80],
    )
    return format_schedule_result(
        action="add",
        title=title,
        due_at=due_at,
        repeat=draft.repeat,
        user_timezone=state.user_timezone,
        ok=True,
    ), True


async def _mutate_one(state: _ReminderFenceCreateState, draft: _ReminderFence) -> tuple[str, bool]:
    title = draft.title.strip()
    due_at = time_context_service.normalize_due_at(draft.due_at, state.user_timezone)
    action = TodoActionItem(
        action=draft.action,
        topic=REMINDER_TOPIC,
        content=title,
        due_at=draft.due_at,
    )
    applied = await apply_todo_actions(
        state.session,
        user_id=state.user_id,
        actions=[action],
        chat_id=state.chat_id,
        user_timezone=state.user_timezone,
    )
    ok = applied > 0
    if ok and draft.action == "delete":
        needle = title.lower()
        state.existing = [
            item for item in state.existing if (item.content or "").strip().lower() != needle
        ]
    return format_schedule_result(
        action=draft.action,
        title=title,
        due_at=due_at,
        repeat=None,
        user_timezone=state.user_timezone,
        ok=ok,
    ), ok


async def materialize_reminder_fences(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    assistant_text: str,
    user_timezone: str | None,
    user_text: str | None = None,
) -> tuple[str, int]:
    """Apply ```reminder fences (create + mutations) and strip them from the reply.

    Returns (updated_text, applied_count). Saves from a valid fence. If the model
    omitted the fence, or emitted an invalid one, an explicit user "remind me …
    today/tomorrow at 6pm" (clock required) is applied so the item still lands
    on Schedule.
    """
    if not _REMINDER_FENCE.search(assistant_text):
        draft = _explicit_user_remind(user_text, user_timezone)
        if draft is None:
            return assistant_text, 0
        state = _ReminderFenceCreateState(
            session=session,
            user_id=user_id,
            chat_id=chat_id,
            user_timezone=user_timezone,
        )
        line, ok = await _create_one(state, draft)
        updated = assistant_text.strip()
        if line:
            updated = f"{updated}\n\n{line}" if updated else line
        if ok:
            await home_service.invalidate_home_cache(user_id)
        return re.sub(r"\n{3,}", "\n\n", updated).strip(), (1 if ok else 0)

    # Load open reminders once (lazily, on the first VALID create fence).
    # Mutations go through apply_todo_actions, which loads its own snapshot.
    state = _ReminderFenceCreateState(
        session=session,
        user_id=user_id,
        chat_id=chat_id,
        user_timezone=user_timezone,
    )

    parts: list[str] = []
    result_lines: list[str] = []
    last = 0
    created_any = False
    for match in _REMINDER_FENCE.finditer(assistant_text):
        parts.append(assistant_text[last : match.start()])
        last = match.end()
        if state.applied >= MAX_TODO_ACTIONS_PER_TURN:
            continue
        draft = _parse_fence(match.group(1))
        if draft is None:
            logger.warning("Invalid reminder fence payload for user_id=%s", state.user_id)
            fallback = _explicit_user_remind(user_text, user_timezone)
            if fallback is None:
                parts.append(_INVALID_FENCE)
                continue
            line, ok = await _create_one(state, fallback)
            result_lines.append(line)
            if ok:
                state.applied += 1
                created_any = True
            else:
                parts.append(_INVALID_FENCE)
            continue
        if draft.action == "add":
            line, ok = await _create_one(state, draft)
            created_any = created_any or ok
        else:
            line, ok = await _mutate_one(state, draft)
        result_lines.append(line)
        if ok:
            state.applied += 1
    parts.append(assistant_text[last:])
    updated = "".join(parts).strip()
    if result_lines:
        updated = f"{updated}\n\n" + "\n".join(result_lines) if updated else "\n".join(result_lines)
    updated = re.sub(r"\n{3,}", "\n\n", updated).strip()
    if created_any:
        await home_service.invalidate_home_cache(user_id)
    return updated, state.applied
