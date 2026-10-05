"""Empty-chat home content — greeting and due reminders."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.models.orm import User
from app.models.schemas import HomeScreenOut, HomeUrgentTodo
from app.modules.home.memory_starters import urgent_subtitle
from app.modules.home.time_starters import greeting
from app.modules.home.util import day_seed, resolve_home_tz
from app.modules.todos import repository as todos_repo
from app.services import reminder_timing

logger = logging.getLogger(__name__)

# Patchable names used by build_home_screen (and underscore aliases for tests).
_resolve_home_tz = resolve_home_tz
_urgent_subtitle = urgent_subtitle


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
    urgent_items = await todos_repo.list_due_soon(
        session,
        user.id,
        before_utc=due_cutoff_utc,
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

    return HomeScreenOut(
        greeting=greeting(user, home_tz),
        subtitle=urgent_subtitle(user, urgent_todos),
        urgent_todos=urgent_todos,
        starters=[],
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
    "build_home_screen",
    "get_home_screen_cached",
    "get_redis_client",
    "greeting",
    "invalidate_home_cache",
    "todos_repo",
]
