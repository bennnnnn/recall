"""The reply's to-dos: the last finalize step, on the finished text.

Chat reads to-dos and never writes them (owner, 2026-11-27): reminders and to-dos are
added and changed in the To-do screen. So:

- a question about what is saved ("what's on my to-do list?") is answered from the saved
  rows, never the model's list (``todos.read_back``);
- a reply that took a request for a change, by a ```reminder or ```todo_link fence or by
  a sentence saying one was made ("Done! I've marked call mom as complete"), becomes the
  server's line and the Open To-do button in the user's language. Beside a fence a model
  wrote "He añadido…" (I've added it) for a change nothing made, so its words go too. A
  fence under a question or a fact to remember is no request: that reply is kept;
- a message of several requests keeps its other answers, and its reminder part gets that
  line under them;
- a question offering to set a reminder goes from every reply, and a "remember …" turn's
  reply claims no to-do (``remember_reply``).

A request the server reads before the model (``todos.todo_screen_reply``) never gets here.
"""

from __future__ import annotations

import logging
import re

from app.core.config import Settings
from app.modules import memory as memory_service
from app.modules import todos as todos_service
from app.modules.chat.remember_reply import without_remember_turn_claims
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.turn_prep.reading import plan_of
from app.modules.turn_reading.writing_kind import writing_request_kind
from app.services.draft_fences import has_draft
from app.services.md_fence_scan import iter_fences, strip_closed_fences
from app.services.prompt_safety import said_by_user
from app.services.subject_scan import without_photo_reading

logger = logging.getLogger(__name__)

# The fences a model writes for a change: the old reminder fence, and the button the
# prompt asks for.
_CHANGE_FENCES = ("reminder", todos_service.TODO_LINK_FENCE)
# A question asks what is saved; a claim beside it may be true ("yes, it's set for 6pm").
_QUESTION_END = re.compile(r"\?\W*$")
_ASKS = re.compile(
    r"^\W*(?:what|when|which|where|who|how|did|do|does|is|are|was|were|have|has|any)\b",
    re.IGNORECASE,
)


def own_words(ctx: StreamContext) -> str:
    """What the user typed or said this turn, as their row keeps it: no attachment excerpt,
    and none of the text read off their photo, which is its content, never a request
    (audit SCAN-03, 2026-11-13). Maths' ``Solve:`` line is the prompt's alone."""
    stored, content = ctx.stored_user_message, ctx.user_message_content or ""
    if isinstance(stored, str) and stored != content:
        return said_by_user(stored)
    return without_photo_reading(content)


async def apply_todo_pass(
    deps: ChatTurnDeps, settings: Settings, ctx: StreamContext, text: str
) -> str:
    """The reply as chat may give it about to-dos: read, never written.

    A failure keeps the text it was given: the finalize passes are done with it.
    """
    try:
        message = own_words(ctx)
        if todos_service.asks_to_read_reminders(message):
            return await _read_back(deps, ctx)
        text = without_remember_turn_claims(message, ctx.user, text)
        return await _without_changes(deps, settings, ctx, message, text)
    except Exception:
        logger.exception("To-do pass failed; keeping the finished reply")
        return text


async def _without_changes(
    deps: ChatTurnDeps, settings: Settings, ctx: StreamContext, message: str, text: str
) -> str:
    prior_user, prior_reply = _prior_text(ctx, "user"), _prior_text(ctx, "assistant")
    plan = plan_of(ctx.user_message_content or "", settings)
    wrote_fence = any(fence.lang in _CHANGE_FENCES for fence in iter_fences(text))
    body = _without_change_fences(text) if wrote_fence else text
    asked = plan.multi and bool(plan.of_kind("reminder"))
    # A model put the button under a question about the list ("ዛሬ ምን አለኝ?") or a fact to
    # remember, too: only a request's fence asks for a change; elsewhere the reply stays
    # as written, its button opening the list (live, 2026-11-27).
    changed = _requests(message) and (
        wrote_fence or await _took_on_a_change(deps, ctx, message, prior_reply, body)
    )
    if not (changed or asked):
        kept = todos_service.without_reminder_offers(text)
        # A reply that was only an offer to set a reminder took the turn for one.
        if kept.strip() or not text.strip():
            return kept
    locale = ctx.user.locale if ctx.user else None
    answer = todos_service.todo_screen_answer(
        todos_service.answer_language(message, prior_user=prior_user, locale=locale)
    )
    if not plan.multi:
        return answer
    kept = todos_service.without_reminder_offers(todos_service.without_claims(body))
    return f"{kept}\n\n{answer}" if kept.strip() else answer


def _requests(message: str) -> bool:
    """The message asks for something done: no question ("is my dentist still on?", "did
    you set it"), no fact for memory to keep. "What's on my list? push gym to friday" ends
    on a request."""
    stripped = message.strip()
    if memory_service.asks_to_remember(stripped) or _QUESTION_END.search(stripped):
        return False
    return "?" in stripped or not _ASKS.match(stripped)


async def _took_on_a_change(
    deps: ChatTurnDeps, ctx: StreamContext, message: str, prior: str, reply: str
) -> bool:
    """The reply says a to-do changed or asks when, as if it would make a change the request
    asked for. After a reply about a change (the To-do button, an old card or result line,
    an offer) "Moved." is enough; a line in a to-do's own words ("mark … done") or naming
    one the user saved ("move gym to 7pm") needs the reminder or the time in the claim. A
    title the reply before also holds is that reply's ("remove the gym days" from a workout
    plan), and a line after a draft edits the draft."""
    if todos_service.follows_todo_reply(prior):
        return _takes_on(reply, about_todos=True)
    # "Buy milk tomorrow at 6pm" answered "I'll remind you tomorrow at 6 PM": a time asked
    # for, and a reminder promised, which nothing sets. A draft or story says what it likes.
    if _promises_a_reminder(message, reply):
        return True
    if not _takes_on(reply, about_todos=False):
        return False
    if todos_service.query_implies_todos(message):
        return True
    if has_draft(prior):
        return False
    async with deps.session_factory() as session:
        title = await deps.todos.saved_todo_named(session, ctx.user_id, message)
    return title is not None and title not in prior.casefold()


def _promises_a_reminder(message: str, reply: str) -> bool:
    return (
        bool(todos_service.find_when(message).spans)
        and writing_request_kind(message) is None
        and todos_service.says_it_will_remind(reply)
    )


def _takes_on(reply: str, *, about_todos: bool) -> bool:
    return todos_service.claims_change(reply, about_todos=about_todos) or todos_service.asks_when(
        reply
    )


def _without_change_fences(text: str) -> str:
    for lang in _CHANGE_FENCES:
        text = strip_closed_fences(text, lang)
    return text.strip()


async def _read_back(deps: ChatTurnDeps, ctx: StreamContext) -> str:
    """The saved to-dos, as the reply to a question about them."""
    timezone = ctx.user_timezone or (ctx.user.timezone if ctx.user else None)
    async with deps.session_factory() as session:
        return await deps.todos.read_back(session, ctx.user_id, timezone)


def _prior_text(ctx: StreamContext, role: str) -> str:
    """The latest earlier message from ``role`` ("" when none). A user's is their own words:
    the prompt frames a photo's text as an untrusted block, and that block asks nothing."""
    for message in reversed(ctx.prompt_messages[:-1]):
        if message.get("role") == role:
            content = message.get("content")
            if not isinstance(content, str):
                return ""
            return said_by_user(content) if role == "user" else content
    return ""
