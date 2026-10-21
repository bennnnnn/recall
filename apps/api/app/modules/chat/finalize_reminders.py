"""The reply's reminder changes: the last finalize step, on the finished text.

This is the finalize step with an effect outside the reply. With reminder cards
on it stores a proposal in Redis and ends the reply with its card; with them
off it writes To-do rows. It runs after every text pass, so no later pass can
fail and throw away a card the user was already offered (ES-03).
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from app.core.config import Settings
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.services.md_fence_scan import last_fence

logger = logging.getLogger(__name__)

_REMINDER_FENCE_LANG = "reminder"
_ASK_WHEN = "When should I remind you?"


def drop_cut_reminder_fence(text: str) -> str:
    """The reply without a ```reminder fence it was cut off inside.

    A reply stopped or dropped mid-fence leaves the fence open, and the reminder
    pass never applies an open one. Finalize closes every open fence before that
    pass runs, so the cut fence goes first (the phone hides reminder fences).
    """
    last = last_fence(text)
    if last is None or last.closed or last.lang != _REMINDER_FENCE_LANG:
        return text
    return text[: last.start].rstrip()


async def apply_reminder_pass(
    deps: ChatTurnDeps,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    text: str,
    outcome: TurnOutcome | None,
) -> str:
    """The reply with its reminder changes applied; ``todos_changed`` when the list changed.

    A failure keeps the text it was given: every pass before this one succeeded.
    """
    try:
        given = text
        text, created = await _materialize(deps, redis, settings, ctx, text)
        # A reply that was only a reminder fence, with nothing saved, must still
        # say something: an empty one kept the streamed fence on the phone.
        if given.strip() and not text.strip():
            text = _ASK_WHEN
        if outcome is not None and not ctx.skip_memory_jobs:
            transcript = f"User: {ctx.user_message_content}\nAssistant: {text}"
            if created > 0 or deps.todos.transcript_implies_todo_sync(transcript):
                outcome.todos_changed = True
    except Exception:
        logger.exception("Reminder pass failed; keeping the finished reply")
    return text


async def _materialize(
    deps: ChatTurnDeps, redis: Redis, settings: Settings, ctx: StreamContext, text: str
) -> tuple[str, int]:
    user = ctx.user
    if user is None:
        async with deps.session_factory() as session:
            user = await deps.users.get_by_id(session, ctx.user_id)
    if user is None:
        return text, 0
    async with deps.session_factory() as session:
        materialized: tuple[str, int] = await deps.todos.materialize_reminder_fences(
            session,
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            assistant_text=text,
            user_timezone=ctx.user_timezone or getattr(user, "timezone", None),
            user_text=ctx.user_message_content,
            # "Mark it done" points at a reminder only after a reply about
            # reminders, or right after a message that asked about them.
            prior_assistant=_prior_text(ctx, "assistant"),
            prior_user=_prior_text(ctx, "user"),
            redis=redis,
            # A reminder change in chat is a card the user taps; nothing is written yet.
            confirm=True,
        )
    return materialized


def _prior_text(ctx: StreamContext, role: str) -> str:
    """The latest earlier message from ``role`` ("" when none)."""
    for message in reversed(ctx.prompt_messages[:-1]):
        if message.get("role") == role:
            content = message.get("content")
            return content if isinstance(content, str) else ""
    return ""
