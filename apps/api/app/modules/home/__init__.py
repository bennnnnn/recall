"""Personalized empty-chat home content — greetings, urgent todos, starters."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
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
from app.modules import memory as memory_service
from app.modules.home.integration_starters import (
    integration_starters as _integration_starters_impl,
)
from app.modules.home.memory_starters import (
    chat_starter,
    memory_starter,
    memory_starter_if_distinct,
    memory_subtitle,
    pick_home_memory,
    urgent_subtitle,
)
from app.modules.home.time_starters import greeting, time_starters, welcome_starters
from app.modules.home.util import (
    MAX_STARTERS,
    day_seed,
    looks_internal,
    resolve_home_tz,
    rotate_list,
    short_phrase,
    texts_overlap,
)
from app.modules.suggestions import repository as suggestions_repo
from app.modules.todos import repository as todos_repo
from app.repositories import chats as chats_repo
from app.services import reminder_timing

logger = logging.getLogger(__name__)

# Patchable names used by build_home_screen (and underscore aliases for tests).
integration_starters = _integration_starters_impl
_resolve_home_tz = resolve_home_tz
_time_starters = time_starters
_memory_starter = memory_starter
_chat_starter = chat_starter
_texts_overlap = texts_overlap
_urgent_subtitle = urgent_subtitle
_looks_internal = looks_internal
_integration_starters = integration_starters


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
    # overlap), so each loader gets its own short-lived session.
    async def load_urgent() -> list:
        return await todos_repo.list_due_soon(
            session,
            user.id,
            before_utc=due_cutoff_utc,
        )

    async def load_memories() -> list[Memory]:
        if not user.memory_enabled:
            return []
        async with SessionLocal() as s:
            return list(await memory_service.load_relevant_memories(s, user, settings))

    async def load_recent_titles() -> list[tuple[str, UUID]]:
        async with SessionLocal() as s:
            recent = await chats_repo.list_for_user(s, user.id, limit=5)
            return [(c.title or "", c.id) for c in recent]

    async def load_integrations() -> list[HomeStarter]:
        async with SessionLocal() as s:
            return await integration_starters(s, user.id, settings, tz=home_tz)

    async def load_suggestions() -> list:
        async with SessionLocal() as s:
            return await suggestions_repo.list_active(s, user.id)

    (
        urgent_items,
        memories,
        recent_chats,
        integration_chips,
        suggestion_items,
    ) = await asyncio.gather(
        load_urgent(),
        load_memories(),
        load_recent_titles(),
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

    home_memory: Memory | None = pick_home_memory(memories)

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

    # No chats / memory / urgents / calendar yet → don't ask
    # "how did today go?" as if we already know the user.
    is_cold_home = (
        not recent_chats and home_memory is None and not urgent_todos and not integration_chips
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

    anchors: list[str] = []
    chat_match = chat_starter(recent_chats, skip_overlapping=anchors)
    if chat_match:
        add(chat_match[0])
        anchors = [*anchors, chat_match[1]]

    if home_memory:
        add(
            memory_starter_if_distinct(
                home_memory,
                skip_overlapping=anchors,
            )
        )

    for item in suggestion_items:
        text = item.text.strip()
        if not text or looks_internal(text):
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

    subtitle = memory_subtitle(home_memory) if home_memory else None
    if urgent_todos and not subtitle:
        subtitle = urgent_subtitle(user, urgent_todos)

    rotated = rotate_list(starters, seed + 17)

    return HomeScreenOut(
        greeting=greeting(user, home_tz),
        subtitle=subtitle,
        urgent_todos=urgent_todos,
        starters=rotated[:MAX_STARTERS],
    )


def _home_generation_key(user_id: UUID) -> str:
    return f"homegen:{user_id}"


def _home_cache_key(user_id: UUID, tz: ZoneInfo, day_seed_value: int, generation: str) -> str:
    # Generation is folded into the key (same pattern as memquery) so INCR
    # makes every tz/day-seed payload unreachable without SCAN. Stale keys
    # expire via home_cache_ttl.
    return f"home:{user_id}:{generation}:{tz.key}:{day_seed_value}"


async def _home_generation(redis: Redis, user_id: UUID) -> str:
    try:
        raw = await redis.get(_home_generation_key(user_id))
    except Exception:
        return "0"
    if raw is None:
        return "0"
    return raw.decode() if isinstance(raw, bytes) else str(raw)


async def invalidate_home_cache(user_id: UUID) -> None:
    """Bump the home cache generation so all tz/day-seed keys miss."""
    try:
        redis = get_redis_client()
        await redis.incr(_home_generation_key(user_id))
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
    redis = get_redis_client()
    generation = await _home_generation(redis, user.id)
    cache_key = _home_cache_key(user.id, home_tz, seed, generation)
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


__all__ = [
    "MAX_STARTERS",
    "build_home_screen",
    "chats_repo",
    "get_home_screen_cached",
    "get_redis_client",
    "greeting",
    "integration_starters",
    "invalidate_home_cache",
    "memory_service",
    "suggestions_repo",
    "time_starters",
    "todos_repo",
    "welcome_starters",
]
