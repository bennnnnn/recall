"""Materialize the turn's To-do changes from its ``reminder`` fences and the user's words.

A turn is read in order: find the fences, match the turn to what the user asked
(their words outrank a missing or mislabeled fence), write, and render the reply
with the app's result lines in place of the fences.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules import home as home_service
from app.modules.todos import proposals, write_log
from app.modules.todos.actions import MAX_TODO_ACTIONS_PER_TURN
from app.modules.todos.recurrence import next_recurring_due
from app.modules.todos.reminder_fence_parse import (
    ReminderFence,
    explicit_user_remind,
    explicitly_declines_reminder_creation,
    find_reminder_fences,
    parse_fence,
)
from app.modules.todos.reminder_writes import ReminderWrites, create_one, load_existing, mutate_one
from app.modules.todos.schemas import RecurrenceRule
from app.modules.todos.spoken_add import (
    about_saved_reminders,
    chat_add_needs_a_stated_time,
    day_for_a_bare_clock,
    due_for_add,
    due_is_past,
    edits_prior_reply,
    parse_spoken_add,
    passed_time_reply,
    pending_add,
    reply_when_nothing_saved,
)
from app.modules.todos.spoken_apply import apply_spoken_change, format_reminder_reading
from app.modules.todos.spoken_change import (
    asks_about_my_reminders,
    asks_to_read_reminders,
    names_reminders,
    parse_spoken_reminder_change,
)
from app.modules.todos.spoken_when import parse_clock_only
from app.services.draft_fences import has_draft

logger = logging.getLogger(__name__)

_INVALID_FENCE = "*Could not save that to-do — the format was invalid.*"
# Each fence in the reply: (start, end, body).
_Spans = list[tuple[int, int, str]]


async def materialize_reminder_fences(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    assistant_text: str,
    user_timezone: str | None,
    user_text: str | None = None,
    prior_assistant: str | None = None,
    prior_user: str | None = None,
    redis: Redis | None = None,
    confirm: bool = False,
) -> tuple[str, int]:
    """Apply the turn's To-do changes, or with ``confirm`` offer them as a card.

    With ``confirm`` the same rules run, but nothing is written: the reply ends
    with a ``reminder_proposal`` card in place of the result lines, and the
    writes wait in Redis for the user's tap. Returns (text, rows written).
    """
    turn = partial(
        _materialize,
        session,
        user_id=user_id,
        chat_id=chat_id,
        assistant_text=proposals.strip_cards(assistant_text),
        user_timezone=user_timezone,
        user_text=user_text,
        prior_assistant=prior_assistant,
        prior_user=prior_user,
    )
    if not confirm or redis is None:
        return await turn()
    with write_log.recording() as writes:
        text, _applied = await turn()
    if not writes:
        return text, 0
    card = await proposals.propose(
        redis,
        user_id=user_id,
        chat_id=chat_id,
        writes=writes,
        user_timezone=user_timezone,
    )
    kept = [line for line in text.split("\n") if not proposals.is_card_line(line, writes)]
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    return (f"{body}\n\n{card}" if body else card), 0


@dataclass(frozen=True)
class _Turn:
    """The reply being finished and the words around it."""

    session: AsyncSession
    user_id: UUID
    chat_id: UUID
    assistant_text: str
    user_timezone: str | None
    user_text: str | None
    prior_assistant: str | None
    prior_user: str | None

    def writes(self) -> ReminderWrites:
        return ReminderWrites(
            session=self.session,
            user_id=self.user_id,
            chat_id=self.chat_id,
            user_timezone=self.user_timezone,
        )


async def _materialize(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    assistant_text: str,
    user_timezone: str | None,
    user_text: str | None = None,
    prior_assistant: str | None = None,
    prior_user: str | None = None,
) -> tuple[str, int]:
    """Apply To-do fences (create + mutations) and strip them from the reply.

    ``prior_assistant`` is the reply before this turn: "mark it done" points at
    a reminder only after a reply about reminders, or right after a message
    (``prior_user``) that asked about them.

    Returns (updated_text, applied_count). Saves from a valid fence. If the model
    omitted the fence, or emitted an invalid one, an explicit user "remind me …
    today/tomorrow at 6pm" (clock required) is applied so the dated To-do is saved.
    """
    turn = _Turn(
        session=session,
        user_id=user_id,
        chat_id=chat_id,
        assistant_text=assistant_text,
        user_timezone=user_timezone,
        user_text=user_text,
        prior_assistant=prior_assistant,
        prior_user=prior_user,
    )
    spans = find_reminder_fences(assistant_text)
    # The user's explicit restraint outranks an LLM-emitted write fence. This
    # is the last boundary before an external state change, so fail closed even
    # when the model misunderstood "don't create a reminder".
    if explicitly_declines_reminder_creation(user_text):
        if not spans:
            return reply_when_nothing_saved(assistant_text, user_text), 0
        kept = _render(assistant_text, spans, [""] * len(spans), [])
        return reply_when_nothing_saved(kept, user_text), 0
    matched = await _match_user_words(turn, spans)
    if matched is not None:
        return matched
    if not spans:
        return await _save_user_remind(turn)
    return await _apply_fences(turn, spans)


async def _match_user_words(turn: _Turn, spans: _Spans) -> tuple[str, int] | None:
    """The turn as the user's own words decide it, or None to go by the fences."""
    # Right after a draft, "add that I'll be late tomorrow at 9am" edits the
    # draft. Only a message that says reminder or task touches reminders.
    if not spans and has_draft(turn.prior_assistant) and not names_reminders(turn.user_text):
        return turn.assistant_text, 0
    # A question about the schedule is answered from the saved rows. The model's
    # list is discarded, including any reminder it invented.
    if asks_to_read_reminders(turn.user_text):
        state = turn.writes()
        await load_existing(state)
        return format_reminder_reading(state.existing, turn.user_timezone), 0
    # The user's words outrank a missing or mislabeled fence. "Mark done"
    # must check the row, not delete it, and the reply is only that result.
    spoken = parse_spoken_reminder_change(turn.user_text, user_timezone=turn.user_timezone)
    if spoken is not None:
        applied = await apply_spoken_change(
            turn.session,
            user_id=turn.user_id,
            chat_id=turn.chat_id,
            user_timezone=turn.user_timezone,
            spoken=spoken,
            user_text=turn.user_text,
            prior_assistant=turn.prior_assistant,
            prior_user=turn.prior_user,
            reply=turn.assistant_text,
        )
        if applied is not None:
            return applied
    answered = await _match_clock_reply(turn)
    if answered is not None:
        return answered
    return await _match_spoken_add(turn, spans)


async def _match_clock_reply(turn: _Turn) -> tuple[str, int] | None:
    """A reply that is only a clock finishes the add the user just described."""
    clock = parse_clock_only(turn.user_text)
    if clock is None:
        return None
    pending = await pending_add(turn.session, turn.chat_id, turn.user_text or "")
    if pending is None:
        return None
    due = due_for_add(
        pending,
        user_timezone=turn.user_timezone,
        hour=clock[0],
        minute=clock[1],
    )
    if due is None or due_is_past(due, user_timezone=turn.user_timezone):
        return passed_time_reply(), 0
    return await _save_spoken_add(turn, title=pending.title, due=due, repeat=pending.repeat)


async def _match_spoken_add(turn: _Turn, spans: _Spans) -> tuple[str, int] | None:
    """An add the user stated with a day and a clock, saved without a fence."""
    stated = parse_spoken_add(turn.user_text)
    if stated is None:
        return None
    if (
        not spans
        and not names_reminders(turn.user_text)
        and not asks_about_my_reminders(turn.prior_user)
        and edits_prior_reply(
            stated.title, prior_assistant=turn.prior_assistant, reply=turn.assistant_text
        )
    ):
        return turn.assistant_text, 0
    # "At 9pm every night" starts tonight, or tomorrow once 9pm has passed.
    if stated.day is None and stated.repeat and stated.hour is not None:
        stated = replace(stated, day="today")
    # "Remind me to plate the dinner at 7pm" is the next 7pm, the same way.
    stated = day_for_a_bare_clock(stated, turn.user_text, user_timezone=turn.user_timezone)
    # The model's own reminder fence, when it wrote one, keeps its cleaner title,
    # unless its time already passed: "at 7pm" said at 9pm is tomorrow's 7pm, and
    # the model's "today 19:00" saved nothing and emptied the reply.
    if spans:
        title = _past_fence_title(spans, turn.user_timezone)
        if title is None:
            return None
        stated = replace(stated, title=title)
    if stated.day is None or stated.hour is None:
        return None
    due = due_for_add(stated, user_timezone=turn.user_timezone)
    if due is not None and stated.repeat and due_is_past(due, user_timezone=turn.user_timezone):
        due = next_recurring_due(
            due, stated.repeat, now=datetime.now(UTC), timezone=turn.user_timezone
        )
    if due is None or due_is_past(due, user_timezone=turn.user_timezone):
        return passed_time_reply(), 0
    return await _save_spoken_add(turn, title=stated.title, due=due, repeat=stated.repeat)


def _past_fence_title(spans: _Spans, user_timezone: str | None) -> str | None:
    """The title of the turn's one add fence when its time already passed."""
    if len(spans) != 1:
        return None
    draft = parse_fence(spans[0][2])
    if draft is None or draft.action != "add" or draft.due_at is None:
        return None
    return draft.title if due_is_past(draft.due_at, user_timezone=user_timezone) else None


async def _save_user_remind(turn: _Turn) -> tuple[str, int]:
    """No fence: save an explicit "remind me … at 6pm", or pass on no false claim."""
    draft = explicit_user_remind(turn.user_text, turn.user_timezone)
    if draft is None:
        # Right after a reply about saved reminders, "Moved **gym** to Sunday"
        # with nothing moved is a false claim.
        about = about_saved_reminders(turn.prior_assistant) or asks_about_my_reminders(
            turn.prior_user
        )
        reply = reply_when_nothing_saved(turn.assistant_text, turn.user_text, about_reminders=about)
        return reply, 0
    line, ok = await create_one(turn.writes(), draft)
    updated = turn.assistant_text.strip()
    if line:
        updated = f"{updated}\n\n{line}" if updated else line
    if ok:
        await home_service.invalidate_home_cache(turn.user_id)
    return _tidy(updated), (1 if ok else 0)


@dataclass(frozen=True)
class _FenceResult:
    """What one fence came to: its result line, and whether it stays as invalid."""

    line: str | None = None
    ok: bool = False
    created: bool = False
    invalid: bool = False


async def _apply_fences(turn: _Turn, spans: _Spans) -> tuple[str, int]:
    """Write each fence, up to the per-turn cap, and render the reply."""
    # Open reminders are loaded once, lazily, on the first create. Mutations go
    # through apply_todo_actions, which loads its own snapshot.
    state = turn.writes()
    in_place: list[str] = []
    result_lines: list[str] = []
    created_any = False
    for _start, _end, body in spans:
        result = _FenceResult()
        if state.applied < MAX_TODO_ACTIONS_PER_TURN:
            result = await _apply_fence(turn, state, body)
        in_place.append(_INVALID_FENCE if result.invalid else "")
        if result.line is not None:
            result_lines.append(result.line)
        if result.ok:
            state.applied += 1
        created_any = created_any or result.created
    updated = _render(turn.assistant_text, spans, in_place, result_lines)
    if created_any:
        await home_service.invalidate_home_cache(turn.user_id)
    if state.applied == 0:
        updated = reply_when_nothing_saved(updated, turn.user_text, about_reminders=True)
    return updated, state.applied


async def _apply_fence(turn: _Turn, state: ReminderWrites, body: str) -> _FenceResult:
    draft = parse_fence(body)
    if draft is None:
        logger.warning("Invalid reminder fence payload for user_id=%s", state.user_id)
        return await _apply_invalid_fence(turn, state)
    if draft.action == "add" and chat_add_needs_a_stated_time(turn.user_text, draft.due_at):
        return await _apply_stated_clock(turn, state)
    if (
        draft.action == "add"
        and turn.user_text is not None
        and draft.due_at is not None
        and due_is_past(draft.due_at, user_timezone=turn.user_timezone)
    ):
        # Saying nothing left an empty reply: the user hears the time passed.
        return _FenceResult(line=passed_time_reply())
    if draft.action == "add":
        line, ok = await create_one(state, draft)
        return _FenceResult(line=line, ok=ok, created=ok)
    line, ok = await mutate_one(state, draft)
    return _FenceResult(line=line, ok=ok)


async def _apply_invalid_fence(turn: _Turn, state: ReminderWrites) -> _FenceResult:
    """An invalid fence saves the user's explicit "remind me … at 6pm", or says it could not."""
    fallback = explicit_user_remind(turn.user_text, turn.user_timezone)
    if fallback is None:
        return _FenceResult(invalid=True)
    line, ok = await create_one(state, fallback)
    return _FenceResult(line=line, ok=ok, created=ok, invalid=not ok)


async def _apply_stated_clock(turn: _Turn, state: ReminderWrites) -> _FenceResult:
    """The fence time was not in the user's message: save only a clock they wrote.

    Otherwise nothing is saved, and the reply asks when.
    """
    fallback = explicit_user_remind(turn.user_text, turn.user_timezone)
    due_at = fallback.due_at if fallback is not None else None
    if fallback is None or due_at is None or due_is_past(due_at, user_timezone=turn.user_timezone):
        return _FenceResult()
    line, ok = await create_one(state, fallback)
    return _FenceResult(line=line, ok=ok, created=ok)


def _render(text: str, spans: _Spans, in_place: list[str], result_lines: list[str]) -> str:
    """The reply with each fence replaced by ``in_place``, then the result lines."""
    parts: list[str] = []
    last = 0
    for (start, end, _body), kept in zip(spans, in_place, strict=True):
        parts.append(text[last:start])
        parts.append(kept)
        last = end
    parts.append(text[last:])
    updated = "".join(parts).strip()
    if result_lines:
        updated = f"{updated}\n\n" + "\n".join(result_lines) if updated else "\n".join(result_lines)
    return _tidy(updated)


def _tidy(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


async def _save_spoken_add(
    turn: _Turn,
    *,
    title: str,
    due: datetime,
    repeat: RecurrenceRule | None,
) -> tuple[str, int]:
    draft = ReminderFence(action="add", title=title, due_at=due)
    draft.repeat = repeat
    line, ok = await create_one(turn.writes(), draft)
    if ok:
        await home_service.invalidate_home_cache(turn.user_id)
    return line, (1 if ok else 0)
