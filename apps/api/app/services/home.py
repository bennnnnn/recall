"""Personalized empty-chat home content — greetings, urgent todos, starters."""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Memory, Project, User
from app.models.schemas import (
    HomeProjectHighlight,
    HomeScreenOut,
    HomeStarter,
    HomeUrgentTodo,
    ProjectStats,
)
from app.repositories import chats as chats_repo
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.repositories import suggestions as suggestions_repo
from app.repositories import todos as todos_repo
from app.services import memory as memory_service
from app.services import time_context as time_context_service

URGENT_TODO_MINUTES = 60
MAX_STARTERS = 5
_HOME_MEMORY_TYPES = frozenset({"project", "focus", "preference"})
_INTERNAL_TEXT = re.compile(
    r"^(?:the\s+)?user(?:'s|\s+name\s+is|\s+email\s+is|\s+id\s+is)\b",
    re.IGNORECASE,
)
_USER_PREFIX = re.compile(
    r"^(?:the\s+)?user(?:'s|\s+is|\s+has|\s+wants\s+to|\s+is\s+trying\s+to|\s+is\s+working\s+on)\s+",
    re.IGNORECASE,
)
_LANGUAGE_LEARNING = re.compile(
    r"\b("
    r"learn(?:ing)?\s+english|english\s+(?:learner|learning|practice|vocabulary|vocab)|"
    r"studying\s+english|improve\s+(?:my\s+)?english|"
    r"learn(?:ing)?\s+(?:a\s+)?(?:new\s+)?language|language\s+learner|"
    r"vocabulary\s+practice|practice\s+(?:my\s+)?english"
    r")\b",
    re.IGNORECASE,
)
from app.services.chat_titles import BORING_CHAT_TITLES

T = TypeVar("T")


def _day_seed(user: User) -> int:
    tz = time_context_service.resolve_timezone(user.timezone)
    day = datetime.now(tz).strftime("%Y-%m-%d")
    digest = hashlib.sha256(f"{user.id}:{day}".encode()).hexdigest()
    return int(digest[:8], 16)


def _rotate_list(items: list[T], seed: int) -> list[T]:
    if len(items) <= 1:
        return items
    rotated = list(items)
    for i in range(len(rotated) - 1, 0, -1):
        j = (seed + i * 7919) % (i + 1)
        rotated[i], rotated[j] = rotated[j], rotated[i]
    return rotated


def _local_hour(user: User) -> int:
    tz = time_context_service.resolve_timezone(user.timezone)
    return datetime.now(tz).hour


def _greeting(user: User) -> str:
    hour = _local_hour(user)
    name = (user.name or "").strip().split()[0] if user.name else None
    if 5 <= hour < 12:
        phrase = "Good morning"
    elif 12 <= hour < 17:
        phrase = "Good afternoon"
    elif 17 <= hour < 22:
        phrase = "Good evening"
    else:
        phrase = "Hey there"
    if name:
        return f"{phrase}, {name}"
    return phrase


def _time_starters(user: User) -> list[HomeStarter]:
    hour = _local_hour(user)
    if 5 <= hour < 12:
        candidates = [
            HomeStarter(
                text="Plan my day",
                prompt="Help me plan my day based on what you know about me.",
                kind="time",
            ),
            HomeStarter(
                text="What's worth focusing on?",
                prompt="What should I focus on today?",
                kind="time",
            ),
        ]
    elif 12 <= hour < 17:
        candidates = [
            HomeStarter(
                text="How's your day?",
                prompt="How's my day looking so far — anything you think I should prioritize?",
                kind="time",
            ),
            HomeStarter(
                text="What are you working on?",
                prompt="What am I trying to get done today?",
                kind="time",
            ),
        ]
    elif 17 <= hour < 22:
        candidates = [
            HomeStarter(
                text="How did today go?",
                prompt="How did my day go? Help me reflect and wrap up loose ends.",
                kind="time",
            ),
            HomeStarter(
                text="Anything left tonight?",
                prompt="What's still open for me to finish tonight?",
                kind="time",
            ),
        ]
    else:
        candidates = [
            HomeStarter(
                text="Still up?",
                prompt="I'm still up — what should I tackle or wind down?",
                kind="time",
            ),
            HomeStarter(
                text="Quick thought",
                prompt="I have a quick thought I want to talk through.",
                kind="time",
            ),
        ]
    return candidates[:2]


def _looks_internal(text: str) -> bool:
    clean = text.strip()
    if not clean:
        return True
    return bool(_INTERNAL_TEXT.match(clean))


def _looks_like_language_learning(text: str) -> bool:
    return bool(_LANGUAGE_LEARNING.search(text.strip()))


def _memory_display_text(text: str) -> str:
    clean = text.strip().rstrip(".")
    cleaned = _USER_PREFIX.sub("", clean).strip()
    return cleaned or clean


def _pick_home_memory(memories: list[Memory]) -> Memory | None:
    for memory in memories:
        if _looks_internal(memory.text):
            continue
        if memory.type in _HOME_MEMORY_TYPES:
            return memory
        if memory.type in ("profile", "fact") and _looks_like_language_learning(memory.text):
            return memory
    return None


def _short_phrase(text: str, *, limit: int = 36) -> str:
    clean = text.strip().rstrip(".")
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1].rstrip()}…"


def _memory_chip_label(memory: Memory, display: str) -> str:
    if _looks_like_language_learning(display):
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


def _memory_starter(memory: Memory) -> HomeStarter | None:
    text = memory.text.strip()
    if not text or _looks_internal(text):
        return None
    display = _memory_display_text(text)
    label = _memory_chip_label(memory, display)
    if memory.type == "project":
        prompt = f"Let's pick up my project again: {display}"
    elif memory.type == "preference":
        prompt = f"Suggest something I'd enjoy — keeping in mind that {display.lower()}"
    elif memory.type == "focus":
        if _looks_like_language_learning(text):
            prompt = f"Help me with my English learning. Context: {display}"
        else:
            prompt = f"Help me make progress on: {display}"
    elif memory.type in ("profile", "fact") and _looks_like_language_learning(text):
        prompt = f"Help me with my English learning. Context: {display}"
    else:
        return None
    return HomeStarter(text=label, prompt=prompt, kind="memory")


def _memory_subtitle(memory: Memory) -> str | None:
    text = memory.text.strip()
    if not text or _looks_internal(text):
        return None
    display = _memory_display_text(text)
    if _looks_like_language_learning(text):
        return "Ready for some English practice?"
    if memory.type == "project":
        return f"Want to keep going on {_short_phrase(display, limit=42)}?"
    if memory.type == "focus":
        return "Ready to pick something back up?"
    return None


def _chat_starter(recent_titles: list[str]) -> HomeStarter | None:
    for title in recent_titles:
        clean = (title or "").strip()
        if not clean or clean.lower() in BORING_CHAT_TITLES:
            continue
        if _looks_internal(clean):
            continue
        return HomeStarter(
            text="Pick up where we left off",
            prompt=f"Let's continue our conversation about {clean}.",
            kind="chat",
        )
    return None


def _format_urgent_due_label(due_at: datetime, user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    due_local = (
        due_at.astimezone(tz)
        if due_at.tzinfo
        else due_at.replace(tzinfo=timezone.utc).astimezone(tz)
    )
    time_str = due_local.strftime("%I:%M %p").lstrip("0")
    if due_local.date() == now.date():
        return f"today at {time_str}"
    if due_local.date() == (now.date() + timedelta(days=1)):
        return f"tomorrow at {time_str}"
    return due_local.strftime("%a %b %d at %I:%M %p").lstrip("0")


def _urgent_subtitle(user: User, urgent_todos: list[HomeUrgentTodo]) -> str | None:
    if not urgent_todos:
        return None
    if len(urgent_todos) > 1:
        return f"{len(urgent_todos)} reminders in the next hour."
    first = urgent_todos[0]
    if first.minutes_until < 0:
        return f"\"{first.content}\" is overdue."
    when = _format_urgent_due_label(first.due_at, user.timezone)
    return f"Coming up: {first.content} {when}."


def _is_language_project(project: Project) -> bool:
    return project.kind in ("language", "vocabulary")


def _project_progress_line(stats: ProjectStats) -> str:
    if stats.total == 0:
        return "I have no words yet — help me add some first."
    return (
        f"{stats.mastered_count} mastered, {stats.new_count} new, "
        f"{stats.learning_count} learning, {stats.due_for_review} due for review."
    )


def _project_starters(project: Project, stats: ProjectStats) -> list[HomeStarter]:
    title = project.title.strip()
    goal = f" Goal: {project.description.strip()}." if project.description and project.description.strip() else ""
    progress = _project_progress_line(stats)

    if _is_language_project(project):
        return []

    return [
        HomeStarter(
            text=f"Continue {title}"[:48],
            prompt=(
                f'Help me with my "{title}" project ({project.kind}).{goal} '
                f"{progress} What should I focus on next?"
            ),
            kind="project",
        ),
    ]


def _project_subtitle(
    project: Project,
    stats: ProjectStats,
    *,
    seed: int,
    has_highlight: bool,
) -> str | None:
    if has_highlight:
        return None
    title = project.title.strip()
    if _is_language_project(project):
        if stats.total == 0:
            return f'Start building your "{title}" word list.'
        if stats.due_for_review > 0:
            variants = [
                (
                    f'You have {stats.total} words in "{title}" — '
                    f"{stats.due_for_review} ready to review."
                ),
                f"{stats.due_for_review} words in \"{title}\" are due for review.",
                f"Review time — {stats.due_for_review} of {stats.total} words in \"{title}\".",
            ]
            return variants[seed % len(variants)]
        return f'You have {stats.total} words in "{title}" — ready to practice?'
    if stats.total > 0:
        return f'Pick up your "{title}" project?'
    return None


def _project_highlight(project: Project) -> HomeProjectHighlight | None:
    if not _is_language_project(project):
        return None
    return HomeProjectHighlight(
        project_id=project.id,
        title=project.title.strip(),
    )


async def _load_project_home_content(
    session: AsyncSession,
    user_id: UUID,
    *,
    seed: int,
) -> tuple[list[HomeStarter], str | None, HomeProjectHighlight | None]:
    projects = await projects_repo.list_for_user(session, user_id, limit=20)
    if not projects:
        return [], None, None

    language_projects = [p for p in projects if _is_language_project(p)]
    primary = language_projects[0] if language_projects else projects[0]
    stats_raw = await project_items_repo.count_stats(session, primary.id, user_id)
    stats = ProjectStats(**stats_raw)
    starters = _project_starters(primary, stats)
    highlight = _project_highlight(primary)
    subtitle = _project_subtitle(
        primary,
        stats,
        seed=seed,
        has_highlight=highlight is not None,
    )
    return starters, subtitle, highlight


async def build_home_screen(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> HomeScreenOut:
    now_utc = datetime.now(timezone.utc)
    due_cutoff_utc = now_utc + timedelta(minutes=URGENT_TODO_MINUTES)
    seed = _day_seed(user)

    async def load_urgent() -> list:
        return await todos_repo.list_due_soon(
            session,
            user.id,
            before_utc=due_cutoff_utc,
        )

    async def load_memories() -> list[Memory]:
        if not user.memory_enabled:
            return []
        return list(await memory_service.load_relevant_memories(session, user, settings))

    async def load_recent_titles() -> list[str]:
        recent = await chats_repo.list_for_user(session, user.id, limit=5)
        return [c.title or "" for c in recent]

    async def load_project_content() -> tuple[list[HomeStarter], str | None, HomeProjectHighlight | None]:
        return await _load_project_home_content(session, user.id, seed=seed)

    async def load_suggestions() -> list:
        return await suggestions_repo.list_active(session, user.id)

    urgent_items, memories, recent_titles, project_content, suggestion_items = await asyncio.gather(
        load_urgent(),
        load_memories(),
        load_recent_titles(),
        load_project_content(),
        load_suggestions(),
    )

    urgent_todos: list[HomeUrgentTodo] = []
    for item in urgent_items:
        if not item.due_at:
            continue
        due_utc = item.due_at
        if due_utc.tzinfo is None:
            due_utc = due_utc.replace(tzinfo=timezone.utc)
        delta = due_utc - now_utc
        urgent_todos.append(
            HomeUrgentTodo(
                id=item.id,
                content=item.content,
                topic=item.topic,
                due_at=due_utc,
                minutes_until=int(delta.total_seconds() // 60),
            )
        )

    home_memory: Memory | None = _pick_home_memory(memories)
    project_starters, project_subtitle, project_highlight = project_content

    starters: list[HomeStarter] = []
    seen_prompts: set[str] = set()

    def add(starter: HomeStarter | None) -> None:
        if not starter or len(starters) >= MAX_STARTERS:
            return
        if _looks_internal(starter.text):
            return
        key = starter.prompt.strip().lower()
        if key in seen_prompts:
            return
        seen_prompts.add(key)
        starters.append(starter)

    time_pool = _time_starters(user)
    if time_pool:
        add(_rotate_list(time_pool, seed)[0])

    add(_chat_starter(recent_titles) if not project_highlight else None)
    if not project_highlight:
        for item in project_starters:
            add(item)
    if home_memory and not project_highlight:
        add(_memory_starter(home_memory))

    for item in suggestion_items:
        text = item.text.strip()
        if not text or _looks_internal(text):
            continue
        add(
            HomeStarter(
                text=_short_phrase(text, limit=48),
                prompt=text,
                kind="general",
            )
        )

    if len(starters) < 3:
        add(
            HomeStarter(
                text="Help me think",
                prompt="I want to talk something through — ask me a good opening question.",
                kind="general",
            )
        )

    if project_highlight:
        subtitle = None
    elif home_memory:
        subtitle = _memory_subtitle(home_memory)
    else:
        subtitle = project_subtitle
    if urgent_todos and not subtitle:
        subtitle = _urgent_subtitle(user, urgent_todos)

    rotated = _rotate_list(starters, seed + 17)

    return HomeScreenOut(
        greeting=_greeting(user),
        subtitle=subtitle,
        project_highlight=project_highlight,
        urgent_todos=urgent_todos,
        starters=rotated[:MAX_STARTERS],
    )
