"""Memory- and chat-continuity home starter chips."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from app.models.orm import Memory, User
from app.models.schemas import HomeProjectHighlight, HomeStarter, HomeUrgentTodo
from app.services import time_context as time_context_service
from app.services.chat_titles import BORING_CHAT_TITLES
from app.services.home.util import (
    _HOME_MEMORY_TYPES,
    _USER_PREFIX,
    CompletedDaily,
    looks_internal,
    looks_like_language_learning,
    overlaps_any,
    short_phrase,
    texts_overlap,
)


def memory_display_text(text: str) -> str:
    clean = text.strip().rstrip(".")
    cleaned = _USER_PREFIX.sub("", clean).strip()
    return cleaned or clean


def pick_home_memory(memories: list[Memory]) -> Memory | None:
    for memory in memories:
        if looks_internal(memory.text):
            continue
        if memory.type in _HOME_MEMORY_TYPES:
            return memory
        if memory.type in ("profile", "fact") and looks_like_language_learning(memory.text):
            return memory
    return None


def memory_chip_label(memory: Memory, display: str) -> str:
    if looks_like_language_learning(display):
        return "Practice English"
    if memory.type == "project":
        return "Keep building"
    if memory.type == "preference":
        return "Find me something good"
    if memory.type == "focus":
        return "Make some progress"
    if memory.type in ("profile", "fact"):
        return "Practice English"
    return "Help me think"


def memory_starter(memory: Memory) -> HomeStarter | None:
    text = memory.text.strip()
    if not text or looks_internal(text):
        return None
    display = memory_display_text(text)
    label = memory_chip_label(memory, display)
    if memory.type == "project":
        prompt = f"Let's pick up my project again: {display}"
    elif memory.type == "preference":
        prompt = f"Suggest something I'd enjoy — keeping in mind that {display.lower()}"
    elif memory.type == "focus":
        if looks_like_language_learning(text):
            prompt = f"Help me with my English learning. Context: {display}"
        else:
            prompt = f"Help me make progress on: {display}"
    elif memory.type in ("profile", "fact") and looks_like_language_learning(text):
        prompt = f"Help me with my English learning. Context: {display}"
    else:
        return None
    return HomeStarter(text=label, prompt=prompt, kind="memory")


def memory_subtitle(memory: Memory) -> str | None:
    text = memory.text.strip()
    if not text or looks_internal(text):
        return None
    display = memory_display_text(text)
    if looks_like_language_learning(text):
        return "Ready for some English practice?"
    if memory.type == "project":
        return f"Want to keep going on {short_phrase(display, limit=42)}?"
    if memory.type == "focus":
        return "Ready to pick something back up?"
    return None


def continuity_anchors(
    *,
    project_starters: list[HomeStarter],
    project_highlight: HomeProjectHighlight | None,
) -> list[str]:
    anchors: list[str] = []
    if project_highlight:
        anchors.append(project_highlight.title.strip())
    for starter in project_starters:
        text = starter.text.strip()
        if text.lower().startswith("continue "):
            anchors.append(text[9:].strip())
        elif text.lower().startswith("start "):
            anchors.append(text[6:].strip())
        elif text.lower().startswith("review "):
            anchors.append(text[7:].strip())
        elif text.lower().startswith("practice "):
            anchors.append(text[9:].strip())
        else:
            anchors.append(text)
    return [anchor for anchor in anchors if anchor]


def chat_starter(
    recent_titles: list[str],
    *,
    skip_overlapping: list[str] | None = None,
) -> tuple[HomeStarter, str] | None:
    skip = skip_overlapping or []
    for title in recent_titles:
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
            ),
            clean,
        )
    return None


def memory_blocked_by_completed_daily(
    memory: Memory,
    completed_daily: list[CompletedDaily],
) -> bool:
    if not completed_daily:
        return False
    display = memory_display_text(memory.text)
    text = memory.text
    language_done = any(kind == "language" for _, kind in completed_daily)
    trivia_done = any(kind == "trivia" for _, kind in completed_daily)

    for title, _kind in completed_daily:
        if texts_overlap(display, title) or texts_overlap(text, title):
            return True

    if language_done and (
        memory.type == "project"
        or looks_like_language_learning(text)
        or looks_like_language_learning(display)
        or re.search(r"\bvocabular", text, re.I)
    ):
        return True

    if (
        trivia_done
        and memory.type == "project"
        and re.search(r"\b(general\s+knowledge|trivia)\b", text, re.I)
    ):
        return True

    return False


def memory_starter_if_distinct(
    memory: Memory,
    *,
    skip_overlapping: list[str],
    completed_daily: list[CompletedDaily] | None = None,
) -> HomeStarter | None:
    if completed_daily and memory_blocked_by_completed_daily(memory, completed_daily):
        return None
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
