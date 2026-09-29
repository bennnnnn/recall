"""Memory- and chat-continuity home starter chips."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.orm import Memory, User
from app.models.schemas import HomeStarter, HomeUrgentTodo
from app.modules import memory as memory_service
from app.modules.home.util import (
    _HOME_MEMORY_TYPES,
    _USER_PREFIX,
    looks_internal,
    overlaps_any,
    short_phrase,
)
from app.services import time_context as time_context_service
from app.services.chat.titles import BORING_CHAT_TITLES


def memory_display_text(text: str) -> str:
    clean = memory_service.strip_memory_as_of(text).rstrip(".")
    cleaned = _USER_PREFIX.sub("", clean).strip()
    return cleaned or clean


def pick_home_memory(memories: list[Memory]) -> Memory | None:
    for memory in memories:
        if looks_internal(memory.text):
            continue
        if memory_service.is_sensitive_memory_text(memory.text):
            continue
        if memory.type in _HOME_MEMORY_TYPES:
            return memory
    return None


def memory_chip_label(memory: Memory) -> str:
    if memory.type == "project":
        return "Keep building"
    if memory.type == "preference":
        return "Find me something good"
    if memory.type == "focus":
        return "Make some progress"
    return "Help me think"


def memory_starter(memory: Memory) -> HomeStarter | None:
    text = memory.text.strip()
    if not text or looks_internal(text) or memory_service.is_sensitive_memory_text(text):
        return None
    display = memory_display_text(text)
    label = memory_chip_label(memory)
    if memory.type == "project":
        prompt = f"Let's pick up my project again: {display}"
    elif memory.type == "preference":
        prompt = f"Suggest something I'd enjoy — keeping in mind that {display.lower()}"
    elif memory.type == "focus":
        prompt = f"Help me make progress on: {display}"
    else:
        return None
    return HomeStarter(text=label, prompt=prompt, kind="memory")


def memory_subtitle(memory: Memory) -> str | None:
    text = memory.text.strip()
    if not text or looks_internal(text):
        return None
    display = memory_display_text(text)
    if memory.type == "project":
        return f"Want to keep going on {short_phrase(display, limit=42)}?"
    if memory.type == "focus":
        return "Ready to pick something back up?"
    return None


def chat_starter(
    recent_chats: list[tuple[str, UUID]],
    *,
    skip_overlapping: list[str] | None = None,
) -> tuple[HomeStarter, str] | None:
    """Build the "Pick up where we left off" starter from the most recent chat.

    ``recent_chats`` is a list of ``(title, chat_id)`` pairs ordered most-
    recent first. The starter carries the ``chat_id`` so the mobile client
    can open the original chat (with its prior message history) instead of
    creating a new empty chat — otherwise the assistant has no context for
    the "continue" prompt and tells the user it doesn't remember the topic.
    """
    skip = skip_overlapping or []
    for title, chat_id in recent_chats:
        clean = (title or "").strip()
        if not clean or clean.lower() in BORING_CHAT_TITLES:
            continue
        if looks_internal(clean):
            continue
        if overlaps_any(clean, skip):
            continue
        return (
            HomeStarter(
                text="Pick up where we left off",
                prompt=f"Let's continue our conversation about {clean}.",
                kind="chat",
                chat_id=chat_id,
            ),
            clean,
        )
    return None


def memory_starter_if_distinct(
    memory: Memory,
    *,
    skip_overlapping: list[str],
) -> HomeStarter | None:
    starter = memory_starter(memory)
    if not starter:
        return None
    display = memory_display_text(memory.text.strip())
    if overlaps_any(display, skip_overlapping) or overlaps_any(memory.text, skip_overlapping):
        return None
    return starter


def format_urgent_due_label(due_at: datetime, user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    due_local = (
        due_at.astimezone(tz) if due_at.tzinfo else due_at.replace(tzinfo=UTC).astimezone(tz)
    )
    time_str = due_local.strftime("%I:%M %p").lstrip("0")
    if due_local.date() == now.date():
        return f"today at {time_str}"
    if due_local.date() == (now.date() + timedelta(days=1)):
        return f"tomorrow at {time_str}"
    return due_local.strftime("%a %b %d at %I:%M %p").lstrip("0")


def urgent_subtitle(user: User, urgent_todos: list[HomeUrgentTodo]) -> str | None:
    if not urgent_todos:
        return None
    if len(urgent_todos) > 1:
        return f"{len(urgent_todos)} reminders in the next hour."
    first = urgent_todos[0]
    if first.minutes_until < 0:
        return f'"{first.content}" is overdue.'
    when = format_urgent_due_label(first.due_at, user.timezone)
    return f"Coming up: {first.content} {when}."
