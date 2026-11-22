"""A reminder the message asks for, read from the chat beside the reply and offered as a card.

The word rules make the card when they can read the request (``todos.reminder_fences``). In
a live QA round (2026-11-22) they read 14 of 30 plain requests: "tmrw at 5 lol" after "When
should I remind you?" was asked again, "Could you remind me tmrw at 5 to call my sister
Margaret" inside a greeting got "I've set a reminder" with nothing saved. Beside the reply,
the Decider is asked whether the message asks for a reminder
(``decider_read.REMINDER_QUESTION``) and, when it does, a model writes the request down
(``todos.model_read``). Finalize waits for it at most ``reminder_read_wait_seconds``, the
server holds it to the user's words and times it (``todos.read_check``), and the reply ends
with the card, in place of an add card the word rules read another way. What is
truly missing (the task, or when) is asked once. A reply on such a turn that still carries no
card never says a reminder is set, saved or added: nothing is saved until the user taps one.

"Did it save?" is answered from the chat: a card the user tapped is saved; one they did not
is not yet, and the reply says so; a request no card was ever offered for gets its card now.
Nothing here raises into a turn.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.modules import todos as todos_service
from app.modules.chat.turn_deps import ChatTurnDeps
from app.services.md_fence_scan import iter_closed_fences, without_fences
from app.services.prompt_safety import said_by_user
from app.services.subject_scan import without_photo_reading

if TYPE_CHECKING:
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

_CARD = "reminder_proposal"
# The chat the read and the checks see: the last messages before this one.
_WINDOW = 8
# Each earlier message the Decider sees, as the turn's read quotes it.
_EARLIER_CHARS = 400
# The last reply asked a question near its end: for this reminder's details, on this turn.
_ASKED_NEAR_END = 300
NOT_SAVED_YET = "It isn't saved yet: tap the reminder card to save it."
NOTHING_SAVED_YET = "No reminder is saved yet."
NOTHING_ASKED = "What should I remind you about, and when?"
NOTHING_SAVED = (
    "I haven't saved a reminder yet. Tell me what to remind you about and when, and I'll show "
    "a card you can tap to save it."
)


@dataclass(frozen=True)
class ReminderRead:
    """What the read made of the turn: the Decider said it asks for a reminder, and the
    model's reading of the request (None: no reading in time)."""

    reading: Any = None


@dataclass(frozen=True)
class PendingRead:
    """The read beside the reply: ``asked`` is the Decider's yes or no, in first (about a
    third of a second); ``task`` ends with the model's reading. Finalize waits long for the
    reading only once the Decider said yes, so a turn that asks for no reminder never waits
    on it."""

    asked: asyncio.Future[bool]
    task: asyncio.Task[ReminderRead | None]


async def asks_for_a_reminder(
    settings: Settings, line: str, earlier: list[tuple[str, str]]
) -> bool:
    """The Decider's yes to ``REMINDER_QUESTION`` on the message; False on any failure (the
    word rules alone read the turn)."""
    from app.gateways.decider_gateway import decide
    from app.gateways.llm_spend import meter_reported_cost
    from app.models import model_catalog
    from app.models.routing_lanes import ROUTING
    from app.modules.chat.decider_read import REMINDER_AT, REMINDER_QUESTION
    from app.modules.chat.turn_decision import decision_messages

    try:
        model = model_catalog.get(ROUTING.decider).model.removeprefix("openrouter/")
        state = decision_messages(line, [(r, t[:_EARLIER_CHARS]) for r, t in earlier[-4:]])
        reply = await decide(
            settings,
            model=model,
            state=state[-1]["content"],
            questions=dict(REMINDER_QUESTION),
            seconds=settings.live_read_timeout_seconds,
        )
        meter_reported_cost(ROUTING.decider, reply.usage.cost)
        odds = reply.answers["reminder"].noul
    except Exception as exc:  # A read is a hint: the word rules decide.
        logger.info("reminder question failed (%s)", type(exc).__name__)
        return False
    return odds is not None and odds >= REMINDER_AT


def own_words(ctx: StreamContext) -> str:
    """What the user typed or said this turn, as their row keeps it: no attachment excerpt,
    and none of the text read off their photo, which is its content, never a request
    (audit SCAN-03, 2026-11-13). Maths' ``Solve:`` line is the prompt's alone."""
    stored, content = ctx.stored_user_message, ctx.user_message_content or ""
    if isinstance(stored, str) and stored != content:
        return said_by_user(stored)
    return without_photo_reading(content)


def conversation(ctx: StreamContext) -> list[tuple[str, str]]:
    """The chat before the turn's message, oldest first, as (role, text); the window may
    end with the message itself (a pending row, or a regenerate's)."""
    rows = [
        (role, content)
        for message in ctx.recent_messages or []
        if (role := getattr(message, "role", None)) in {"user", "assistant"}
        and isinstance(content := getattr(message, "content", None), str)
        and content.strip()
    ]
    line = " ".join((ctx.user_message_content or "").split())
    if rows and rows[-1][0] == "user" and " ".join(rows[-1][1].split()) == line:
        rows.pop()
    return [(role, said_by_user(text) if role == "user" else text) for role, text in rows][
        -_WINDOW:
    ]


def _local_now(ctx: StreamContext) -> datetime:
    from app.services import time_context as time_context_service

    zone = ctx.user_timezone or (ctx.user.timezone if ctx.user else None)
    return datetime.now(time_context_service.resolve_timezone(zone))


def start_reminder_read(settings: Settings, ctx: StreamContext) -> PendingRead | None:
    """The read, begun beside the reply: the Decider says whether the message asks for a
    reminder and, when it does, a model writes the request down. Never in a chat that only
    reads its to-dos (another language), nor on a turn the server answered itself."""
    line = ctx.user_message_content or ""
    if not (settings.reminder_read_enabled and settings.live_read_enabled) or not line.strip():
        return None
    if ctx.instant_reply is not None or not settings.openrouter_api_key:
        return None
    asked: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
    return PendingRead(asked=asked, task=asyncio.create_task(_read(settings, ctx, asked)))


async def _read(
    settings: Settings, ctx: StreamContext, asked: asyncio.Future[bool]
) -> ReminderRead | None:
    try:
        earlier = conversation(ctx)
        prior_user = next((text for role, text in reversed(earlier) if role == "user"), "")
        locale = ctx.user.locale if ctx.user else None
        words = own_words(ctx)
        if todos_service.writes_todos_in_todo_screen(words, prior_user=prior_user, locale=locale):
            return None
        yes = await asks_for_a_reminder(settings, words, earlier)
        asked.set_result(yes)
        if not yes:
            return None
        now = _local_now(ctx)
        return ReminderRead(
            reading=await todos_service.read_reminder_chat(settings, earlier, words, now=now)
        )
    finally:
        if not asked.done():
            asked.set_result(False)


def stop_reminder_read(ctx: StreamContext) -> None:
    pending = getattr(ctx, "reminder_read", None)
    if pending is not None and not pending.task.done():
        pending.task.cancel()


async def _reading(ctx: StreamContext, settings: Settings) -> ReminderRead | None:
    """The read, when it is in within the wait; None otherwise (or when it says no)."""
    pending: PendingRead | None = getattr(ctx, "reminder_read", None)
    if pending is None:
        return None
    # The Decider's answer, waited for only briefly: it is in long before a reply ends.
    await asyncio.wait([pending.asked], timeout=settings.reminder_decide_wait_seconds)
    if not pending.asked.done() or pending.asked.cancelled() or not pending.asked.result():
        stop_reminder_read(ctx)
        return None
    task = pending.task
    await asyncio.wait([task], timeout=settings.reminder_read_wait_seconds)
    if not task.done():
        stop_reminder_read(ctx)
        logger.info("reminder read: not in time, the word rules' reply stands")
        return None
    if task.cancelled() or task.exception() is not None:
        return None
    return task.result()


def _last_card(earlier: list[tuple[str, str]]) -> dict[str, Any] | None:
    """The latest reminder card the chat's replies offered, as its JSON."""
    for role, content in reversed(earlier):
        if role != "assistant":
            continue
        for _start, _end, body in reversed(list(iter_closed_fences(content, _CARD))):
            try:
                card = json.loads(body)
            except json.JSONDecodeError:
                return None
            return card if isinstance(card, dict) else None
    return None


def _asked_before(earlier: list[tuple[str, str]]) -> bool:
    """The last reply ended on a question: the details it asked for are being given now."""
    last = next((text for role, text in reversed(earlier) if role == "assistant"), "")
    return "?" in without_fences(last, " ").rstrip()[-_ASKED_NEAR_END:]


async def finish_with_the_read(
    deps: ChatTurnDeps,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    given: str,
    text: str,
) -> str:
    """The reply on a turn the read says asks for a reminder: the read's card (in place of
    an add card the word rules read otherwise), its one question, or the reply without a
    claim of a reminder set. ``given``: the model's reply; ``text``: the
    reply as the word rules left it, maybe with their card."""
    read = await _reading(ctx, settings)
    if read is None:
        return text
    reading = read.reading
    if reading is not None and reading.request == "none":
        # The model read no reminder in it: the word rules' reply stands.
        return text
    earlier = conversation(ctx)
    lines = [content for role, content in earlier if role == "user"] + [own_words(ctx)]
    zone = ctx.user_timezone or (ctx.user.timezone if ctx.user else None)
    checked = todos_service.check_reading(
        reading, lines, user_timezone=zone, asked_before=_asked_before(earlier)
    )
    actions = _card_actions(text)
    if reading is not None and reading.request == "status":
        # "Did it save?" changes nothing: a card the word rules made for it ("did it" read
        # as done) is not offered.
        return await _status(deps, redis, ctx, earlier, _without_card(text), checked, zone)
    if actions - {"add"}:
        # A change to a saved reminder (done, moved, deleted) is the word rules' card.
        return text
    if checked is not None and checked.adds:
        # The read's request outranks an add the word rules read another way ("an hour
        # before my dinner at 7" saved "an hour before my dinner" at 7 PM).
        card = await _card(deps, redis, ctx, given, checked.adds, zone)
        if card is not None:
            return card
    if actions:
        return text
    if checked is not None and checked.ask:
        return _with_question(text, checked.ask)
    return honest(text)


def _card_actions(text: str) -> set[str]:
    """What the reply's card would do: "add", "complete", "set_due", …"""
    actions: set[str] = set()
    for _start, _end, body in iter_closed_fences(text, _CARD):
        try:
            items = json.loads(body).get("items", [])
        except (json.JSONDecodeError, AttributeError):
            continue
        actions.update(str(item.get("action")) for item in items if isinstance(item, dict))
    return actions


def _without_card(text: str) -> str:
    from app.services.md_fence_scan import strip_closed_fences

    return strip_closed_fences(text, _CARD).strip()


async def _status(
    deps: ChatTurnDeps,
    redis: Redis,
    ctx: StreamContext,
    earlier: list[tuple[str, str]],
    text: str,
    checked: Any,
    zone: str | None,
) -> str:
    """ "Did it save?": a tapped card is saved, an untapped one is not yet, and a request no
    card was offered for gets one now."""
    card = _last_card(earlier)
    if card is not None and card.get("status") == "saved":
        return text
    if card is not None:
        body = todos_service.without_claims(text, about=True)
        if body.strip() == text.strip():
            return text
        return f"{body}\n\n{NOT_SAVED_YET}".strip()
    if checked is not None and checked.adds:
        offered = await _card(deps, redis, ctx, "", checked.adds, zone)
        if offered is not None:
            return f"{NOT_SAVED_YET}\n\n{offered}"
    # No card was ever offered and the request cannot be read whole: nothing is saved, and
    # the one thing missing is asked ("Just a vibe thing, I don't have a reminder tool").
    question = checked.ask if checked is not None and checked.ask else NOTHING_ASKED
    return f"{NOTHING_SAVED_YET} {question}"


async def _card(
    deps: ChatTurnDeps,
    redis: Redis,
    ctx: StreamContext,
    reply: str,
    adds: Any,
    zone: str | None,
) -> str | None:
    try:
        async with deps.session_factory() as session:
            offered: str | None = await todos_service.offer_adds(
                session,
                user_id=ctx.user_id,
                chat_id=ctx.chat_id,
                reply=todos_service.without_denials(reply),
                adds=adds,
                user_timezone=zone,
                redis=redis,
            )
            await session.commit()
    except Exception:
        logger.exception("Reminder card from the read failed; keeping the reply")
        return None
    return offered


def _with_question(text: str, question: str) -> str:
    """The reply, claims out, asking the one thing still missing. A question of when goes
    when the time was said and only the task is missing ("remind me tomorrow at 5" asked
    "When should I remind you?"); another question of the reply's stays and is the one."""
    body = todos_service.without_claims(text, about=True)
    if question != todos_service.ASK_WHEN:
        body = todos_service.without_when_questions(body)
    if "?" in without_fences(body, " "):
        return body
    return f"{body}\n\n{question}" if body.strip() else question


def honest(text: str) -> str:
    """A reply on a reminder turn with no card claims no reminder (nothing is saved until
    the user taps one), and never says the app cannot make one: English chat can."""
    body = todos_service.without_reminder_denials(todos_service.without_claims(text, about=True))
    if body.strip() == text.strip():
        return text
    return f"{body}\n\n{NOTHING_SAVED}" if body.strip() else NOTHING_SAVED
