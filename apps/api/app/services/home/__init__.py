"""Personalized empty-chat home content — greetings, urgent todos, starters."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.models.orm import Memory, User
from app.models.schemas import (
    HomeScreenOut,
    HomeStarter,
    HomeUrgentTodo,
)
from app.repositories import chats as chats_repo
from app.repositories import suggestions as suggestions_repo
from app.repositories import todos as todos_repo
from app.services import memory as memory_service
from app.services import reminder_timing
from app.services.home import project_starters as project_starters_mod
from app.services.home.integration_starters import (
    integration_starters as _integration_starters_impl,
)
from app.services.home.memory_starters import (
    chat_starter,
    continuity_anchors,
    memory_blocked_by_completed_daily,
    memory_starter,
    memory_starter_if_distinct,
    memory_subtitle,
    pick_home_memory,
    urgent_subtitle,
)
from app.services.home.project_starters import (
    load_project_home_content as _load_project_home_content_impl,
)
from app.services.home.project_starters import project_starters
from app.services.home.time_starters import greeting, time_starters, welcome_starters
from app.services.home.util import (
    MAX_STARTERS,
    ProjectHomeContent,
    day_seed,
    looks_internal,
    looks_like_language_learning,
    resolve_home_tz,
    rotate_list,
    short_phrase,
    texts_overlap,
)

# Re-exported for tests that patch home_service.projects_repo / project_items_repo.
projects_repo = project_starters_mod.projects_repo
project_items_repo = project_starters_mod.project_items_repo

logger = logging.getLogger(__name__)

# Patchable names used by build_home_screen (and underscore aliases for tests).
load_project_home_content = _load_project_home_content_impl
integration_starters = _integration_starters_impl
_resolve_home_tz = resolve_home_tz
_time_starters = time_starters
_memory_blocked_by_completed_daily = memory_blocked_by_completed_daily
_memory_starter = memory_starter
_chat_starter = chat_starter
_texts_overlap = texts_overlap
_urgent_subtitle = urgent_subtitle
_looks_internal = looks_internal
_project_starters = project_starters
_integration_starters = integration_starters
_load_project_home_content = load_project_home_content


async def build_home_screen(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
) -> HomeScreenOut:
    home_tz = resolve_home_tz(user, client_timezone)
    now_utc = datetime.now(UTC)
    # Urgent window = the user's reminder lead (5/10/15/30 min), unified with
    # badge + notification semantics. Overdue todos are included by list_due_soon
    # (any due_at <= cutoff). Replaces the former flat 60-minute window.
    lead_minutes = reminder_timing.resolve_reminder_lead_minutes(user.reminder_lead_minutes)
    due_cutoff_utc = now_utc + timedelta(minutes=lead_minutes)
    seed = day_seed(user, home_tz)

    # These loads are independent and run concurrently — but an AsyncSession
    # can only run one operation at a time (asyncpg raises InterfaceError on
    # overlap), so each loader gets its own short-lived session. The heaviest
    # loader (project content, several sequential queries) keeps the request
    # session so the gather uses it exactly once.
    async def load_urgent() -> list:
        async with SessionLocal() as s:
            return await todos_repo.list_due_soon(
                s,
                user.id,
                before_utc=due_cutoff_utc,
            )

    async def load_memories() -> list[Memory]:
        if not user.memory_enabled:
            return []
        async with SessionLocal() as s:
            return list(await memory_service.load_relevant_memories(s, user, settings))

    async def load_recent_titles() -> list[str]:
        async with SessionLocal() as s:
            recent = await chats_repo.list_for_user(s, user.id, limit=5)
            return [c.title or "" for c in recent]

    async def load_project_content() -> ProjectHomeContent:
        return await load_project_home_content(session, user.id, seed=seed, home_tz=home_tz)

    async def load_integrations() -> list[HomeStarter]:
        async with SessionLocal() as s:
            return await integration_starters(s, user.id, settings, tz=home_tz)

    async def load_suggestions() -> list:
        async with SessionLocal() as s:
            return await suggestions_repo.list_active(s, user.id)

    # Project highlight is the common path — load it with the always-needed
    # loaders first, then only fetch memories/recent chats when there is no
    # highlight (those starters are skipped when a highlight is present).
    (
        urgent_items,
        project_content,
        integration_chips,
        suggestion_items,
    ) = await asyncio.gather(
        load_urgent(),
        load_project_content(),
        load_integrations(),
        load_suggestions(),
    )

    memories: list[Memory] = []
    recent_titles: list[str] = []
    if project_content.highlight is None:
        memories, recent_titles = await asyncio.gather(
            load_memories(),
            load_recent_titles(),
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

    has_language_project = project_content.has_language_project
    home_memory: Memory | None = pick_home_memory(
        memories, has_language_project=has_language_project
    )
    project_chips = project_content.starters
    project_subtitle = project_content.subtitle
    project_highlight = project_content.highlight
    completed_daily = project_content.completed_daily

    starters: list[HomeStarter] = []
    seen_prompts: set[str] = set()

    def add(starter: HomeStarter | None) -> None:
        if not starter or len(starters) >= MAX_STARTERS:
            return
        if looks_internal(starter.text):
            return
        key = starter.prompt.strip().lower()
        if key in seen_prompts:
            return
        seen_prompts.add(key)
        starters.append(starter)

    # No chats / learning / memory / urgents / calendar yet → don't ask
    # "how did today go?" as if we already know the user.
    is_cold_home = (
        project_highlight is None
        and not project_chips
        and not recent_titles
        and home_memory is None
        and not urgent_todos
        and not integration_chips
    )
    if is_cold_home:
        for item in welcome_starters():
            add(item)
    else:
        time_pool = time_starters(user, home_tz)
        if time_pool:
            add(rotate_list(time_pool, seed)[0])

    for item in integration_chips:
        add(item)

    anchors = continuity_anchors(
        project_starters=project_chips,
        project_highlight=project_highlight,
    )

    if not project_highlight:
        for item in project_chips:
            add(item)

    chat_skip = [
        *anchors,
        *(title for title, _kind in completed_daily),
    ]
    chat_match = (
        None if project_highlight else chat_starter(recent_titles, skip_overlapping=chat_skip)
    )
    if chat_match:
        add(chat_match[0])
        anchors = [*anchors, chat_match[1]]

    if home_memory and not project_highlight:
        add(
            memory_starter_if_distinct(
                home_memory,
                skip_overlapping=anchors,
                completed_daily=completed_daily,
                has_language_project=has_language_project,
            )
        )

    for item in suggestion_items:
        text = item.text.strip()
        if not text or looks_internal(text):
            continue
        # Don't nudge English practice from stale LLM suggestions after class delete.
        if looks_like_language_learning(text) and not has_language_project:
            continue
        add(
            HomeStarter(
                id=str(item.id),
                text=short_phrase(text, limit=48),
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
    elif home_memory and not memory_blocked_by_completed_daily(home_memory, completed_daily):
        subtitle = memory_subtitle(home_memory)
    else:
        subtitle = project_subtitle
    if urgent_todos and not subtitle:
        subtitle = urgent_subtitle(user, urgent_todos)

    rotated = rotate_list(starters, seed + 17)

    return HomeScreenOut(
        greeting=greeting(user, home_tz),
        subtitle=subtitle,
        project_highlight=project_highlight,
        urgent_todos=urgent_todos,
        starters=rotated[:MAX_STARTERS],
    )


def _home_cache_key(user_id: UUID, tz: ZoneInfo, day_seed_value: int) -> str:
    return f"home:{user_id}:{tz.key}:{day_seed_value}"


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
    home_tz = resolve_home_tz(user, client_timezone)
    seed = day_seed(user, home_tz)
    cache_key = _home_cache_key(user.id, home_tz, seed)
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
