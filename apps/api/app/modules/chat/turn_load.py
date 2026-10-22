"""What a turn reads before it runs: the user, the chat, quota, recent history and the model.

The prepare lock is already held. Both loads wait for the previous turn's save
first, so history never misses the reply before this one.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import user_cache
from app.core.config import Settings
from app.exceptions import ChatNotFoundError, ConsentRequiredError
from app.models import model_catalog
from app.models.orm import Chat, User
from app.modules.account import consent
from app.modules.chat.finalize_registry import wait_for_pending_finalize
from app.modules.chat.prompt_constants import (
    active_lesson_step,
    is_lightweight_chat_turn,
    is_short_reply,
)
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_prep import RegenerateBackup
from app.modules.chat.turn_prep.mode import _TurnMode, classify_turn_mode
from app.modules.chat.turn_settle import seed_usage_from_db
from app.modules.chat.turn_timing import TurnTimingTracker
from app.services import model_health
from app.services.routing import last_user_turn

logger = logging.getLogger(__name__)


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
    # The window read once here; the prompt reuses it (``omit_message_ids`` drops the
    # reply being replaced), and the model health read beside it.
    recent: list[Any]
    unhealthy: frozenset[str] = frozenset()


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
    deps: ChatTurnDeps,
    redis: Redis,
    timing: TurnTimingTracker,
    user_id: UUID,
    user: User | None,
) -> User:
    if (
        user is not None
        and consent.has_ai_data_consent(user)
        and await user_cache.is_current(redis, user_id)
    ):
        timing.mark_phase("user_ready")
        return user
    # A user handed in from the request cache can trail an agreement made, or a consent,
    # memory or web-search switch turned off, on another machine: read the row, and keep
    # it for the next turn (a WebSocket turn has no request cache to fill it).
    generation = await user_cache.read_generation(redis, user_id)
    async with deps.session_factory() as session:
        loaded = await deps.users.get_by_id(session, user_id)
    if loaded is None:
        raise ChatNotFoundError("User not found.")
    _require_consent(loaded)
    user_cache.remember_read(loaded, generation)
    timing.mark_phase("user_ready")
    return loaded


def _require_consent(user: User) -> None:
    """No turn sends anything to outside AI services before the account agreed.

    Raised before the user message is saved or quota is reserved, so the error
    frame says ``user_message_saved: false`` and the prepare lock is released.
    """
    if not consent.has_ai_data_consent(user):
        raise ConsentRequiredError()


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
        # Unknown counts as missing: the turn re-reads today's total from the DB.
        logger.warning("Daily usage probe failed user_id=%s", user_id, exc_info=True)
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
        _load_user(deps, redis, timing, user_id, user),
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
    # Read from the window just loaded: "yes" after a question, or "make it shorter"
    # after a draft, used to read the messages again in a session of its own.
    turn_mode = classify_turn_mode(recent, content)
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
    (user, chat, recent, prior_count, last_user), unhealthy = await asyncio.gather(
        _read_regenerate_rows(deps, settings, user_id=user_id, chat_id=chat_id),
        _unhealthy_models(redis, settings),
    )
    last = recent[-1]
    model = deps.plan.resolve_regenerate_model(
        user, model_alias, last_user.content, last.model, settings
    )
    backup: RegenerateBackup | None = None
    omit_message_ids: set[UUID] | None = None
    if last.role == "assistant":
        backup = RegenerateBackup(content=last.content, model=last.model, message_id=last.id)
        omit_message_ids = {last.id}
    return RegenerateTurn(
        user=user,
        chat=chat,
        model=model,
        content=last_user.content,
        prior_count=prior_count,
        turn_mode=classify_turn_mode(recent, last_user.content),
        backup=backup,
        omit_message_ids=omit_message_ids,
        recent=recent,
        unhealthy=unhealthy,
    )


async def _read_regenerate_rows(
    deps: ChatTurnDeps, settings: Settings, *, user_id: UUID, chat_id: UUID
) -> tuple[User, Chat, list[Any], int, Any]:
    """The user, the chat, the recent window and the count, in one session.

    The last message and the last user message come from the window; it used to read
    the messages four to six times.
    """
    window = settings.recent_message_window
    async with deps.session_factory() as session:
        user = await deps.users.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")
        _require_consent(user)
        chat = await deps.chats.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")
        recent = await deps.messages.list_recent(session, chat_id, limit=window)
        if not recent:
            raise ChatNotFoundError("No messages to regenerate.")
        last_user = next((m for m in reversed(recent) if m.role == "user"), None)
        if last_user is None:
            # A window of replies only (rare): the user's line is further back.
            last_user = await deps.messages.get_last_user(session, chat_id)
        if last_user is None:
            raise ChatNotFoundError("No user message to regenerate from.")
        prior_count = await _prior_count_for_window(
            recent,
            window,
            count_for_chat=deps.messages.count_for_chat,
            session=session,
            chat_id=chat_id,
        )
    return user, chat, recent, prior_count, last_user
