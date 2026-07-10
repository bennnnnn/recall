"""Personalized empty-chat home content — greetings, urgent todos, starters."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Literal, NamedTuple, TypeVar
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.redis import get_redis_client
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
from app.services import calendar as calendar_service
from app.services import daily_learning, learning_insights, reminder_timing
from app.services import email as email_service
from app.services import memory as memory_service
from app.services import time_context as time_context_service

logger = logging.getLogger(__name__)

MAX_STARTERS = 5
MORNING_START_HOUR = 5
EMAIL_END_HOUR = 11  # show inbox chip until 11:00
CALENDAR_TODAY_END_HOUR = 12  # "Today's calendar" until noon
CALENDAR_TOMORROW_START_HOUR = 12
CALENDAR_TOMORROW_END_HOUR = 22  # hide calendar chips late evening
REFLECT_START_HOUR = 15  # "How did today go?" from 3 PM
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
    r"vocabulary\s+practice|practice\s+(?:my\s+)?english|"
    r"vocabulary\s+learning|vocabular\w*"
    r")\b",
    re.IGNORECASE,
)
from app.services.chat_titles import BORING_CHAT_TITLES

T = TypeVar("T")

CompletedDaily = tuple[str, Literal["language", "trivia"]]


class ProjectHomeContent(NamedTuple):
    starters: list[HomeStarter]
    subtitle: str | None
    highlight: HomeProjectHighlight | None
    completed_daily: list[CompletedDaily]


def _resolve_home_tz(user: User, client_timezone: str | None = None) -> ZoneInfo:
    return time_context_service.resolve_timezone(
        time_context_service.effective_timezone(user.timezone, client_timezone)
    )


def _local_hour_for_tz(tz: ZoneInfo) -> int:
    return datetime.now(tz).hour


def _day_seed(user: User, tz: ZoneInfo) -> int:
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


def _local_hour(user: User, tz: ZoneInfo | None = None) -> int:
    return _local_hour_for_tz(tz or time_context_service.resolve_timezone(user.timezone))


def _greeting(user: User, tz: ZoneInfo) -> str:
    hour = _local_hour_for_tz(tz)
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


def _time_starters(user: User, tz: ZoneInfo) -> list[HomeStarter]:
    hour = _local_hour_for_tz(tz)
    if MORNING_START_HOUR <= hour < CALENDAR_TODAY_END_HOUR:
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
    elif CALENDAR_TODAY_END_HOUR <= hour < REFLECT_START_HOUR:
        candidates = [
            HomeStarter(
                text="What are you working on?",
                prompt="What am I trying to get done today?",
                kind="time",
            ),
            HomeStarter(
                text="What's left today?",
                prompt="What's still open for me to finish today?",
                kind="time",
            ),
        ]
    elif REFLECT_START_HOUR <= hour < 22:
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


def _normalize_overlap_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _overlap_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", _normalize_overlap_text(text))
        if len(token) >= 3
    }


def _texts_overlap(a: str, b: str) -> bool:
    left = _normalize_overlap_text(a)
    right = _normalize_overlap_text(b)
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    left_tokens = _overlap_tokens(left)
    right_tokens = _overlap_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    shared = left_tokens & right_tokens
    if len(shared) >= 2:
        return True
    shorter = min(len(left_tokens), len(right_tokens))
    return len(shared) >= 1 and len(shared) / shorter >= 0.5


def _continuity_anchors(
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


def _overlaps_any(text: str, anchors: list[str]) -> bool:
    return any(_texts_overlap(text, anchor) for anchor in anchors)


def _chat_starter(
    recent_titles: list[str],
    *,
    skip_overlapping: list[str] | None = None,
) -> tuple[HomeStarter, str] | None:
    skip = skip_overlapping or []
    for title in recent_titles:
        clean = (title or "").strip()
        if not clean or clean.lower() in BORING_CHAT_TITLES:
            continue
        if _looks_internal(clean):
            continue
        if _overlaps_any(clean, skip):
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


def _memory_blocked_by_completed_daily(
    memory: Memory,
    completed_daily: list[CompletedDaily],
) -> bool:
    if not completed_daily:
        return False
    display = _memory_display_text(memory.text)
    text = memory.text
    language_done = any(kind == "language" for _, kind in completed_daily)
    trivia_done = any(kind == "trivia" for _, kind in completed_daily)

    for title, _kind in completed_daily:
        if _texts_overlap(display, title) or _texts_overlap(text, title):
            return True

    if language_done and (
        memory.type == "project"
        or _looks_like_language_learning(text)
        or _looks_like_language_learning(display)
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


def _memory_starter_if_distinct(
    memory: Memory,
    *,
    skip_overlapping: list[str],
    completed_daily: list[CompletedDaily] | None = None,
) -> HomeStarter | None:
    if completed_daily and _memory_blocked_by_completed_daily(memory, completed_daily):
        return None
    starter = _memory_starter(memory)
    if not starter:
        return None
    display = _memory_display_text(memory.text.strip())
    if _overlaps_any(display, skip_overlapping) or _overlaps_any(memory.text, skip_overlapping):
        return None
    return starter


def _format_urgent_due_label(due_at: datetime, user_timezone: str | None) -> str:
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


def _urgent_subtitle(user: User, urgent_todos: list[HomeUrgentTodo]) -> str | None:
    if not urgent_todos:
        return None
    if len(urgent_todos) > 1:
        return f"{len(urgent_todos)} reminders in the next hour."
    first = urgent_todos[0]
    if first.minutes_until < 0:
        return f'"{first.content}" is overdue.'
    when = _format_urgent_due_label(first.due_at, user.timezone)
    return f"Coming up: {first.content} {when}."


def _is_language_project(project: Project) -> bool:
    return project.kind in ("language", "vocabulary")


def _is_trivia_project(project: Project) -> bool:
    return project.kind == "trivia"


def _is_daily_home_project(project: Project) -> bool:
    return _is_language_project(project) or _is_trivia_project(project)


def _daily_home_kind(project: Project) -> Literal["language", "trivia"]:
    return "trivia" if _is_trivia_project(project) else "language"


def _project_progress_line(project: Project, stats: ProjectStats) -> str:
    if _is_language_project(project):
        if stats.total == 0:
            return "I have no words yet — help me add some first."
        return (
            f"{stats.mastered_count} mastered, {stats.new_count} new, "
            f"{stats.learning_count} learning, {stats.due_for_review} due for review."
        )
    if _is_trivia_project(project):
        if stats.total == 0:
            return "I have not answered any trivia questions yet."
        return (
            f"{stats.mastered_count} facts learned, {stats.mastered_today} correct today, "
            f"{stats.learning_count} still learning."
        )
    if stats.total == 0:
        return "I have not started this project yet."
    return f"I have {stats.total} items tracked on this project."


def _project_chip_label(project: Project, stats: ProjectStats) -> str:
    title = project.title.strip()
    if _is_daily_home_project(project):
        daily_goal = daily_learning.resolve_daily_goal(project)
        if stats.mastered_today >= daily_goal:
            return ""
        if stats.total == 0 or stats.mastered_today == 0:
            return f"Start {title}"[:48]
        return f"Continue {title}"[:48]
    if stats.total == 0:
        return f"Start {title}"[:48]
    return f"Continue {title}"[:48]


def _project_starters(project: Project, stats: ProjectStats) -> list[HomeStarter]:
    title = project.title.strip()
    goal = (
        f" Goal: {project.description.strip()}."
        if project.description and project.description.strip()
        else ""
    )
    progress = _project_progress_line(project, stats)
    label = _project_chip_label(project, stats)

    if _is_language_project(project):
        daily_goal = daily_learning.resolve_daily_goal(project)
        if stats.mastered_today >= daily_goal:
            return []
        remaining = max(0, daily_goal - stats.mastered_today)
        if stats.total == 0:
            prompt = (
                f'Help me start my "{title}" vocabulary project.{goal} '
                "Suggest how to add my first words and a simple first session."
            )
        elif stats.mastered_today == 0:
            prompt = (
                f'Help me start today\'s "{title}" vocabulary session.{goal} {progress} '
                f"My daily goal is {daily_goal} words. Quiz and teach in chat — "
                "you pick the format each turn (multiple choice, sentences, definitions, etc.). "
                "Prioritize words due for review, then new and learning words."
            )
        elif stats.due_for_review > 0:
            prompt = (
                f'Help me review my "{title}" vocabulary.{goal} {progress} '
                f"I still need {remaining} more mastered today to hit my daily goal of "
                f"{daily_goal}. Quiz words that are due — do not add fresh words yet."
            )
        else:
            prompt = (
                f'Help me with my "{title}" vocabulary.{goal} {progress} '
                f"I need {remaining} more mastered today (daily goal: {daily_goal}). "
                "Quiz my new and learning words first — only add fresh words if I still "
                "need them for today's goal."
            )
    elif _is_trivia_project(project):
        daily_goal = daily_learning.resolve_daily_goal(project)
        if stats.mastered_today >= daily_goal:
            return []
        remaining = max(0, daily_goal - stats.mastered_today)
        if stats.total == 0:
            prompt = (
                f'Start my daily "{title}" general-knowledge session.{goal} '
                f"Quiz me in chat — one question at a time, {daily_goal} correct today. "
                "You choose the format (multiple choice, open-ended, etc.). Begin now."
            )
        elif stats.mastered_today == 0:
            prompt = (
                f'Start my daily "{title}" general-knowledge session.{goal} {progress} '
                f"Quiz me in chat — one question at a time until {daily_goal} correct today. "
                "You choose the format each turn."
            )
        else:
            prompt = (
                f'Continue my daily "{title}" session.{goal} {progress} '
                f"I need {remaining} more correct today (daily goal: {daily_goal}). "
                "Ask the next question in chat — you pick the format."
            )
    elif stats.total == 0:
        prompt = (
            f'Help me start my "{title}" project ({project.kind}).{goal} '
            "I have not begun yet — suggest a simple first step."
        )
    else:
        prompt = (
            f'Help me with my "{title}" project ({project.kind}).{goal} '
            f"{progress} What should I focus on next?"
        )

    return [
        HomeStarter(
            text=label,
            prompt=prompt,
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
                f'{stats.due_for_review} words in "{title}" are due for review.',
                f'Review time — {stats.due_for_review} of {stats.total} words in "{title}".',
            ]
            return variants[seed % len(variants)]
        return f'You have {stats.total} words in "{title}" — ready to practice?'
    if _is_trivia_project(project):
        daily_goal = daily_learning.resolve_daily_goal(project)
        if stats.total == 0:
            return f'Start your daily "{title}" quiz.'
        if stats.mastered_today > 0:
            return f'{stats.mastered_today}/{daily_goal} correct on "{title}" today — keep going?'
        return f'Ready for today\'s "{title}" quiz?'
    if stats.total > 0:
        return f'Pick up your "{title}" project?'
    return None


def _project_highlight(
    project: Project,
    stats: ProjectStats,
    *,
    home_tz: ZoneInfo,
    project_items: list | None = None,
) -> HomeProjectHighlight | None:
    if not _is_daily_home_project(project):
        return None
    daily_goal = daily_learning.resolve_daily_goal(project)
    cue = daily_learning.daily_home_cue(
        total=stats.total,
        mastered_today=stats.mastered_today,
        pending_today=stats.pending_today,
        learning_count=stats.learning_count,
        due_for_review=stats.due_for_review,
        daily_goal=daily_goal,
        last_mastery=stats.last_mastery_at,
        home_tz=home_tz,
    )
    if cue is None:
        return None
    enriched = learning_insights.enrich_learning_stats(
        stats.model_dump(),
        project=project,
        items=project_items or [],
        timezone_name=str(home_tz.key),
        daily_history=daily_learning.build_daily_history(
            project_items or [],
            timezone_name=str(home_tz.key),
            daily_goal=daily_goal,
            active_since=project.created_at,
        )
        if project_items
        else None,
    )
    return HomeProjectHighlight(
        project_id=project.id,
        title=project.title.strip(),
        kind=_daily_home_kind(project),
        daily_goal=daily_goal,
        mastered_today=stats.mastered_today,
        cue=cue,
        streak_days=int(enriched.get("streak_days") or 0),
        days_inactive=enriched.get("days_inactive"),
        due_for_review=stats.due_for_review,
        suggested_level=enriched.get("suggested_level"),
    )


async def _load_project_home_content(
    session: AsyncSession,
    user_id: UUID,
    *,
    seed: int,
    home_tz: ZoneInfo,
) -> ProjectHomeContent:
    projects = await projects_repo.list_for_user(session, user_id, limit=20)
    if not projects:
        return ProjectHomeContent([], None, None, [])

    daily_projects = sorted(
        [p for p in projects if _is_daily_home_project(p)],
        key=lambda p: (0 if _is_language_project(p) else 1, p.title.casefold()),
    )
    tz_name = str(home_tz.key)

    if daily_projects:
        project_ids = [candidate.id for candidate in daily_projects]
        stats_by_project = await project_items_repo.count_stats_by_project(
            session,
            project_ids,
            timezone_by_project={candidate.id: tz_name for candidate in daily_projects},
        )
        all_items = await project_items_repo.list_for_projects(session, project_ids)
        items_by_project: dict[UUID, list] = {pid: [] for pid in project_ids}
        for item in all_items:
            items_by_project.setdefault(item.project_id, []).append(item)
        completed_daily: list[CompletedDaily] = []
        for candidate in daily_projects:
            stats = ProjectStats.model_validate(stats_by_project.get(candidate.id, {}))
            daily_goal = daily_learning.resolve_daily_goal(candidate)
            if stats.mastered_today >= daily_goal:
                completed_daily.append((candidate.title.strip(), _daily_home_kind(candidate)))
                continue
            highlight = _project_highlight(
                candidate,
                stats,
                home_tz=home_tz,
                project_items=items_by_project.get(candidate.id, []),
            )
            if highlight is not None:
                starters: list[HomeStarter] = []
                subtitle = _project_subtitle(
                    candidate,
                    stats,
                    seed=seed,
                    has_highlight=True,
                )
                return ProjectHomeContent(starters, subtitle, highlight, completed_daily)
        return ProjectHomeContent([], None, None, completed_daily)

    primary = projects[0]
    stats_by_primary = await project_items_repo.count_stats_by_project(
        session,
        [primary.id],
        timezone_by_project={primary.id: tz_name},
    )
    stats = ProjectStats.model_validate(stats_by_primary.get(primary.id, {}))
    highlight = _project_highlight(primary, stats, home_tz=home_tz)
    completed_daily = []
    if highlight is None and _is_daily_home_project(primary):
        daily_goal = daily_learning.resolve_daily_goal(primary)
        if stats.mastered_today >= daily_goal:
            completed_daily = [(primary.title.strip(), _daily_home_kind(primary))]
    starters = _project_starters(primary, stats)
    subtitle = _project_subtitle(
        primary,
        stats,
        seed=seed,
        has_highlight=highlight is not None,
    )
    return ProjectHomeContent(starters, subtitle, highlight, completed_daily)


async def _integration_starters(
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
    *,
    tz: ZoneInfo,
) -> list[HomeStarter]:
    """Surface connected calendar/Gmail as home chips — time-of-day aware."""
    hour = _local_hour_for_tz(tz)
    starters: list[HomeStarter] = []

    if settings.google_calendar_enabled and await calendar_service.is_connected(session, user_id):
        if MORNING_START_HOUR <= hour < CALENDAR_TODAY_END_HOUR:
            starters.append(
                HomeStarter(
                    text="Today's calendar",
                    prompt=(
                        "What's on my calendar for the rest of today and what should I prepare for?"
                    ),
                    kind="general",
                )
            )
        elif CALENDAR_TOMORROW_START_HOUR <= hour < CALENDAR_TOMORROW_END_HOUR:
            starters.append(
                HomeStarter(
                    text="Tomorrow's calendar",
                    prompt=(
                        "What's on my calendar tomorrow and what should I prepare ahead of time?"
                    ),
                    kind="general",
                )
            )

    if (
        settings.gmail_enabled
        and await email_service.is_connected(session, user_id)
        and MORNING_START_HOUR <= hour < EMAIL_END_HOUR
    ):
        starters.append(
            HomeStarter(
                text="Email to handle",
                prompt=(
                    "Check my inbox — anything I need to reply to or follow up on this morning?"
                ),
                kind="general",
            )
        )
    return starters


async def build_home_screen(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
) -> HomeScreenOut:
    home_tz = _resolve_home_tz(user, client_timezone)
    now_utc = datetime.now(UTC)
    # Urgent window = the user's reminder lead (5/10/15/30 min), unified with
    # badge + notification semantics. Overdue todos are included by list_due_soon
    # (any due_at <= cutoff). Replaces the former flat 60-minute window.
    lead_minutes = reminder_timing.resolve_reminder_lead_minutes(user.reminder_lead_minutes)
    due_cutoff_utc = now_utc + timedelta(minutes=lead_minutes)
    seed = _day_seed(user, home_tz)

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

    async def load_project_content() -> ProjectHomeContent:
        return await _load_project_home_content(session, user.id, seed=seed, home_tz=home_tz)

    async def load_integrations() -> list[HomeStarter]:
        return await _integration_starters(session, user.id, settings, tz=home_tz)

    async def load_suggestions() -> list:
        return await suggestions_repo.list_active(session, user.id)

    (
        urgent_items,
        memories,
        recent_titles,
        project_content,
        integration_starters,
        suggestion_items,
    ) = await asyncio.gather(
        load_urgent(),
        load_memories(),
        load_recent_titles(),
        load_project_content(),
        load_integrations(),
        load_suggestions(),
    )

    urgent_todos: list[HomeUrgentTodo] = []
    for item in urgent_items:
        if not item.due_at:
            continue
        due_utc = item.due_at
        if due_utc.tzinfo is None:
            due_utc = due_utc.replace(tzinfo=UTC)
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
    project_starters = project_content.starters
    project_subtitle = project_content.subtitle
    project_highlight = project_content.highlight
    completed_daily = project_content.completed_daily

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

    time_pool = _time_starters(user, home_tz)
    if time_pool:
        add(_rotate_list(time_pool, seed)[0])

    for item in integration_starters:
        add(item)

    continuity_anchors = _continuity_anchors(
        project_starters=project_starters,
        project_highlight=project_highlight,
    )

    if not project_highlight:
        for item in project_starters:
            add(item)

    chat_skip = [
        *continuity_anchors,
        *(title for title, _kind in completed_daily),
    ]
    chat_match = (
        None if project_highlight else _chat_starter(recent_titles, skip_overlapping=chat_skip)
    )
    if chat_match:
        add(chat_match[0])
        continuity_anchors = [*continuity_anchors, chat_match[1]]

    if home_memory and not project_highlight:
        add(
            _memory_starter_if_distinct(
                home_memory,
                skip_overlapping=continuity_anchors,
                completed_daily=completed_daily,
            )
        )

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
    elif home_memory and not _memory_blocked_by_completed_daily(home_memory, completed_daily):
        subtitle = _memory_subtitle(home_memory)
    else:
        subtitle = project_subtitle
    if urgent_todos and not subtitle:
        subtitle = _urgent_subtitle(user, urgent_todos)

    rotated = _rotate_list(starters, seed + 17)

    return HomeScreenOut(
        greeting=_greeting(user, home_tz),
        subtitle=subtitle,
        project_highlight=project_highlight,
        urgent_todos=urgent_todos,
        starters=rotated[:MAX_STARTERS],
    )


def _home_cache_key(user_id: UUID, tz: ZoneInfo, day_seed: int) -> str:
    return f"home:{user_id}:{tz.key}:{day_seed}"


def _home_cache_prefix(user_id: UUID) -> str:
    return f"home:{user_id}:"


async def invalidate_home_cache(user_id: UUID) -> None:
    """Drop cached home payloads for all timezones/day seeds for this user."""
    try:
        redis = get_redis_client()
        prefix = _home_cache_prefix(user_id)
        batch: list[str] = []
        async for key in redis.scan_iter(match=f"{prefix}*", count=200):
            batch.append(key if isinstance(key, str) else key.decode())
            if len(batch) >= 200:
                await redis.delete(*batch)
                batch.clear()
        if batch:
            await redis.delete(*batch)
    except Exception:
        logger.debug("Home cache invalidation failed", exc_info=True)


async def get_home_screen_cached(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
) -> HomeScreenOut:
    home_tz = _resolve_home_tz(user, client_timezone)
    day_seed = _day_seed(user, home_tz)
    cache_key = _home_cache_key(user.id, home_tz, day_seed)
    redis = get_redis_client()
    try:
        cached = await redis.get(cache_key)
        if cached:
            return HomeScreenOut.model_validate_json(cached)
    except Exception:
        logger.debug("Home screen cache read failed", exc_info=True)

    screen = await build_home_screen(
        session,
        user,
        settings,
        client_timezone=client_timezone,
    )
    try:
        await redis.set(
            cache_key,
            screen.model_dump_json(),
            ex=max(30, settings.home_cache_ttl),
        )
    except Exception:
        logger.debug("Home screen cache write failed", exc_info=True)
    return screen
