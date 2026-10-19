"""What a turn reads before it runs: the user, the chat, quota, recent history and the model.

The prepare lock is already held. Both loads wait for the previous turn's save
first, so history never misses the reply before this one.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.exceptions import ChatNotFoundError
from app.models.orm import Chat, User
from app.modules.chat.finalize_registry import wait_for_pending_finalize
from app.modules.chat.post_turn import seed_usage_from_db
from app.modules.chat.prompt_constants import (
    active_lesson_step,
    is_lightweight_chat_turn,
    is_short_reply,
)
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_prep import RegenerateBackup
from app.modules.chat.turn_prep.mode import _classify_turn_mode, _TurnMode
from app.modules.chat.turn_timing import TurnTimingTracker
from app.services import model_catalog, model_health
from app.services.routing import last_user_turn


@dataclass(frozen=True)
class NewTurn:
    user: User
    chat: Chat
    daily_limit: int
    recent: list[Any]
    prior_count: int
    turn_mode: _TurnMode
    model: str
    # Chat models whose provider is failing; routing above already skipped them.
    unhealthy: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RegenerateTurn:
    user: User
    chat: Chat
    model: str
    content: str
    prior_count: int
    turn_mode: _TurnMode
    backup: RegenerateBackup | None
    omit_message_ids: set[UUID] | None


async def _prior_count_for_window(
    recent: list[Any],
    window: int,
    *,
    count_for_chat: Callable[[AsyncSession, UUID], Awaitable[int]],
    session: AsyncSession,
    chat_id: UUID,
) -> int:
    """Exact count only when the recent window is full (older rows may exist)."""
    if len(recent) < window:
        return len(recent)
    raw_count = await count_for_chat(session, chat_id)
    return raw_count if isinstance(raw_count, int) else len(recent)


async def _load_user(
    deps: ChatTurnDeps, timing: TurnTimingTracker, user_id: UUID, user: User | None
) -> User:
    if user is not None:
        timing.mark_phase("user_ready")
        return user
    async with deps.session_factory() as session:
        loaded = await deps.users.get_by_id(session, user_id)
    if loaded is None:
        raise ChatNotFoundError("User not found.")
    timing.mark_phase("user_ready")
    return loaded


async def _load_chat(
    deps: ChatTurnDeps,
    timing: TurnTimingTracker,
    *,
    chat_id: UUID,
    user_id: UUID,
    chat: Chat | None,
) -> Chat:
    if chat is not None:
        timing.mark_phase("chat_ready")
        return chat
    remembered = deps.chats.peek_recent_chat(chat_id, user_id)
    if remembered is not None:
        timing.mark_phase("chat_ready")
        return remembered
    async with deps.session_factory() as session:
        loaded = await deps.chats.get_by_id(session, chat_id, user_id)
    if loaded is None:
        raise ChatNotFoundError("Chat not found.")
    timing.mark_phase("chat_ready")
    return loaded


async def _needs_usage_seed(
    deps: ChatTurnDeps, redis: Redis, timing: TurnTimingTracker, user_id: UUID, skip: bool
) -> bool:
    if skip:
        timing.mark_phase("quota_probe_ready")
        return False
    try:
        missing = not await deps.quota.has_daily_usage_key(redis, str(user_id))
    except Exception:
        missing = True
    timing.mark_phase("quota_probe_ready")
    return missing


async def _load_account(
    deps: ChatTurnDeps,
    redis: Redis,
    settings: Settings,
    timing: TurnTimingTracker,
    *,
    user_id: UUID,
    chat_id: UUID,
    user: User | None,
    chat: Chat | None,
    skip_usage_seed: bool,
) -> tuple[User, int, Chat]:
    # User ownership, chat ownership, and the Redis quota probe are
    # independent. Live simulator timing showed the old user->chat serial DB
    # reads dominating this lane, so overlap them. Each DB read gets its own
    # AsyncSession; SQLAlchemy AsyncSession itself is intentionally not used
    # concurrently.
    loaded_user, loaded_chat, need_usage_seed = await asyncio.gather(
        _load_user(deps, timing, user_id, user),
        _load_chat(deps, timing, chat_id=chat_id, user_id=user_id, chat=chat),
        _needs_usage_seed(deps, redis, timing, user_id, skip_usage_seed),
    )
    if need_usage_seed:
        async with deps.session_factory() as session:
            await seed_usage_from_db(redis, session, user_id)
    timing.mark_phase("quota_seed_ready")
    limit = deps.quota.daily_limit_for_user(loaded_user, settings)
    timing.mark_phase("account_quota_ready")
    return loaded_user, limit, loaded_chat


async def _load_history_after_finalize(
    deps: ChatTurnDeps,
    redis: Redis,
    settings: Settings,
    timing: TurnTimingTracker,
    chat_id: UUID,
) -> tuple[list[Any], int]:
    # History must observe the previous assistant commit, but it does not
    # depend on the current turn's user/chat lookup. Run both lanes
    # concurrently so a remote DB round trip is paid once in wall time, not
    # once for account/chat and again for recent messages.
    await wait_for_pending_finalize(chat_id, redis, require_complete=True)
    timing.mark_phase("previous_finalize_ready")
    async with deps.session_factory() as session:
        window = settings.recent_message_window
        recent = await deps.messages.list_recent(session, chat_id, limit=window)
        prior_count = await _prior_count_for_window(
            recent,
            window,
            count_for_chat=deps.messages.count_for_chat,
            session=session,
            chat_id=chat_id,
        )
    timing.mark_phase("history_ready")
    return recent, prior_count


async def load_new_turn(
    deps: ChatTurnDeps,
    redis: Redis,
    settings: Settings,
    timing: TurnTimingTracker,
    *,
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model_alias: str | None,
    user: User | None,
    chat: Chat | None,
    skip_usage_seed: bool,
) -> NewTurn:
    # Account/quota and history are independent once the previous turn is
    # committed. A greeting does not need the recent window before the model
    # starts — that extra Neon read was on the first-token path. A short reply
    # ("no" to "Understood?") answers the last turn, so it always loads the
    # window; without it the model greets instead.
    obvious_greeting = is_lightweight_chat_turn(content) and not is_short_reply(content)
    load_account = partial(
        _load_account,
        deps,
        redis,
        settings,
        timing,
        user_id=user_id,
        chat_id=chat_id,
        user=user,
        chat=chat,
        skip_usage_seed=skip_usage_seed,
    )
    if obvious_greeting:
        await wait_for_pending_finalize(chat_id, redis, require_complete=True)
        timing.mark_phase("previous_finalize_ready")
        (loaded_user, daily_limit, loaded_chat), unhealthy = await asyncio.gather(
            load_account(), _unhealthy_models(redis, settings)
        )
        recent: list[Any] = []
        prior_count = 0
        timing.mark_phase("history_ready")
    else:
        (
            (loaded_user, daily_limit, loaded_chat),
            (recent, prior_count),
            unhealthy,
        ) = await asyncio.gather(
            load_account(),
            _load_history_after_finalize(deps, redis, settings, timing, chat_id),
            _unhealthy_models(redis, settings),
        )
    # Only short confirmation turns touch the DB here; ordinary lightweight
    # greetings classify synchronously, so opening a fresh AsyncSession has no
    # checkout/network cost on the common path.
    async with deps.session_factory() as session:
        turn_mode = await _classify_turn_mode(session, loaded_chat, content)
    prior_user, prior_model = last_user_turn(recent)
    model = deps.plan.resolve_user_model_override(
        loaded_user,
        model_alias,
        content,
        settings,
        prior_user=prior_user,
        prior_model=prior_model,
        lesson_active=active_lesson_step(recent) is not None,
        unhealthy=unhealthy,
    )
    timing.mark_phase("user_quota")
    return NewTurn(
        user=loaded_user,
        chat=loaded_chat,
        daily_limit=daily_limit,
        recent=recent,
        prior_count=prior_count,
        turn_mode=turn_mode,
        model=model,
        unhealthy=unhealthy,
    )


async def _unhealthy_models(redis: Redis, settings: Settings) -> frozenset[str]:
    """Chat models whose provider is failing, read beside the account (the pool
    needs the user, so every selectable model is read)."""
    aliases = [model.id for model in model_catalog.selectable_models()]
    return await model_health.unhealthy_aliases(redis, settings, aliases)


async def load_regenerate_turn(
    deps: ChatTurnDeps,
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    model_alias: str | None,
) -> RegenerateTurn:
    # Last-message reads must see the committed assistant. Overlapping that
    # load with wait_for_pending_finalize can regenerate from a stale last
    # row. New turns gather wait with user/quota instead — prepare reads
    # messages only after both finish.
    await wait_for_pending_finalize(chat_id, redis, require_complete=True)
    backup: RegenerateBackup | None = None
    omit_message_ids: set[UUID] | None = None
    async with deps.session_factory() as session:
        user = await deps.users.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")
        chat = await deps.chats.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")
        last = await deps.messages.get_last(session, chat_id)
        if last is None:
            raise ChatNotFoundError("No messages to regenerate.")
        last_user = await deps.messages.get_last_user(session, chat_id)
        if last_user is None:
            raise ChatNotFoundError("No user message to regenerate from.")
        model = deps.plan.resolve_regenerate_model(
            user, model_alias, last_user.content, last.model, settings
        )
        content = last_user.content
        prior_count = await deps.messages.count_for_chat(session, chat_id)
        if last.role == "assistant":
            backup = RegenerateBackup(content=last.content, model=last.model, message_id=last.id)
            omit_message_ids = {last.id}
        turn_mode = await _classify_turn_mode(session, chat, content)
    return RegenerateTurn(
        user=user,
        chat=chat,
        model=model,
        content=content,
        prior_count=prior_count,
        turn_mode=turn_mode,
        backup=backup,
        omit_message_ids=omit_message_ids,
    )
