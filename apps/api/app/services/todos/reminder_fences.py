"""Materialize ```reminder JSON fences from assistant replies."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
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
from sqlalchemy.exc import IntegrityError
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
_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_DAY_NAMES = frozenset(("today", "tomorrow", *_WEEKDAYS))
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


def _find_phrase(haystack: str, needle: str, *, start: int = 0) -> int:
    """Return the index of ``needle`` as a whole-word phrase, or -1."""
    pos = start
    needle_len = len(needle)
    while True:
        idx = haystack.find(needle, pos)
        if idx < 0:
            return -1
        before_ok = idx == 0 or not haystack[idx - 1].isalpha()
        after = idx + needle_len
        after_ok = after >= len(haystack) or not haystack[after].isalpha()
        if before_ok and after_ok:
            return idx
        pos = idx + 1


def _skip_spaces(text: str, index: int) -> int:
    length = len(text)
    while index < length and text[index].isspace():
        index += 1
    return index


def _parse_ampm(text: str, index: int) -> tuple[str, int] | None:
    length = len(text)
    index = _skip_spaces(text, index)
    if index >= length:
        return None
    letter = text[index].lower()
    if letter not in ("a", "p"):
        return None
    index += 1
    if index < length and text[index] == ".":
        index += 1
    if index >= length or text[index].lower() != "m":
        return None
    index += 1
    if index < length and text[index] == ".":
        index += 1
    return letter, index


def _parse_clock(text: str, index: int) -> tuple[int, int] | None:
    """Parse ``H[:MM] am/pm`` starting at ``index``. Linear digit walk, no regex."""
    length = len(text)
    index = _skip_spaces(text, index)
    if index >= length or not text[index].isdigit():
        return None
    hour = 0
    digits = 0
    while index < length and text[index].isdigit() and digits < 2:
        hour = hour * 10 + (ord(text[index]) - 48)
        index += 1
        digits += 1
    minute = 0
    if index < length and text[index] == ":":
        index += 1
        if index + 1 >= length or not (text[index].isdigit() and text[index + 1].isdigit()):
            return None
        minute = (ord(text[index]) - 48) * 10 + (ord(text[index + 1]) - 48)
        index += 2
    parsed = _parse_ampm(text, index)
    if parsed is None:
        return None
    meridiem, _end = parsed
    if hour == 12:
        hour = 0 if meridiem == "a" else 12
    elif meridiem == "p":
        hour += 12
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def _last_at_separator(haystack: str, start: int) -> int:
    """Index of the last `` at `` separator at or after ``start``, or -1."""
    last = -1
    pos = start
    while True:
        idx = haystack.find(" at ", pos)
        if idx < 0:
            return last
        last = idx
        pos = idx + 1


def _due_date_for_day(day_name: str, now: datetime) -> date | None:
    if day_name == "today":
        return now.date()
    if day_name == "tomorrow":
        return now.date() + timedelta(days=1)
    try:
        weekday = _WEEKDAYS.index(day_name)
    except ValueError:
        return None
    delta = (weekday - now.weekday()) % 7
    return now.date() + timedelta(days=delta)


def parse_spoken_remind(
    user_text: str | None,
    *,
    user_timezone: str | None = None,
    now: datetime | None = None,
) -> tuple[str, datetime] | None:
    """Linear parse of ``remind me [to] TITLE DAY at H[:MM] am/pm``.

    DAY is today, tomorrow, or a weekday name. Missing clocks are not invented.
    """
    if not user_text:
        return None
    lowered = user_text.lower()
    remind_at = _find_phrase(lowered, "remind me")
    if remind_at < 0:
        return None
    cursor = _skip_spaces(user_text, remind_at + len("remind me"))
    if lowered.startswith("to", cursor) and (
        cursor + 2 >= len(lowered) or not lowered[cursor + 2].isalpha()
    ):
        cursor = _skip_spaces(user_text, cursor + 2)
    title_start = cursor
    last_at = _last_at_separator(lowered, title_start)
    if last_at < 0:
        return None
    clock = _parse_clock(user_text, last_at + len(" at "))
    if clock is None:
        return None
    before = user_text[title_start:last_at].rstrip()
    if not before:
        return None
    split = before.rfind(" ")
    day_raw = before[split + 1 :] if split >= 0 else before
    day_token = day_raw.strip().strip("\"'").rstrip(".,;:").lower()
    if day_token not in _DAY_NAMES:
        return None
    title = (before[:split] if split >= 0 else "").strip().strip("\"'").rstrip(".,;:")
    if not title:
        return None
    tz = time_context_service.resolve_timezone(user_timezone)
    when = now.astimezone(tz) if now is not None else datetime.now(tz)
    day = _due_date_for_day(day_token, when)
    if day is None:
        return None
    hour, minute = clock
    due = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
    return title[:500], due


def _explicit_user_remind(
    user_text: str | None, user_timezone: str | None
) -> _ReminderFence | None:
    """Parse 'remind me … today/tomorrow/weekday at 6pm' from the user — never invent a clock."""
    parsed = parse_spoken_remind(user_text, user_timezone=user_timezone)
    if parsed is None:
        return None
    title, due = parsed
    return _ReminderFence(action="add", title=title, due_at=due)


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
    try:
        new_todo = await todos_repo.create(
            state.session,
            user_id=state.user_id,
            content=title,
            topic=REMINDER_TOPIC,
            chat_id=state.chat_id,
            due_at=due_at,
            recurrence_rule=draft.repeat,
        )
    except IntegrityError as exc:
        if not todos_repo.is_open_content_due_conflict(exc):
            raise
        await state.session.rollback()
        existing = await todos_repo.get_open_dated_duplicate(
            state.session, state.user_id, content=title, due_at=due_at
        )
        if existing is None:
            raise
        saved_due = existing.due_at if existing.due_at is not None else due_at
        return format_schedule_result(
            action="add",
            title=title,
            due_at=saved_due,
            repeat=getattr(existing, "recurrence_rule", None) or draft.repeat,
            user_timezone=state.user_timezone,
            ok=True,
        ), True
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
        recurrence_rule=draft.repeat if draft.action == "set_due" else None,
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
        repeat=draft.repeat if draft.action == "set_due" else None,
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
