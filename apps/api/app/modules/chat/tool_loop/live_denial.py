"""A first answer that says it can't see live data is asked again, with search.

"Perfect. totally unrelated but did the bears win today" was answered "I can't check live
scores" (live chat, 2026-10-25): the word rules read the line as a statement, so neither
the tool loop nor the reply's own call could search. Two rules that read the user's words
caught everyday statements ("went to the gym today but was too tired") in review. The
reply decides instead. When the first call carried no tool and its answer says it cannot
get live facts, the answer is taken back and the model is asked again with
``web_search``. The tool-loop path offers the retry only after the turn's read called
the answer settled, and only when the spend cap allows tools
(``StreamContext.denial_retry_tools``); ``may_check`` leaves out the turns whose denial
can be no claim about public facts.

The denial was a pattern of English openings ("I can't check live …" starting a sentence
of a short reply). On a Pro phone test (2026-11-11) a five-item list said "I can't check
live rankings from here, so this list reflects widely cited reputation" mid-sentence and
went out as it was; "Let me check the current list for you" with no list after it, and
the same in Spanish or Amharic, were never caught. Perplexity's Decider now reads the
reply's prose instead (about 0.3 s and $0.00002 a reply). On the 62 replies of
``tests/behavior/live_denial_corpus.json`` it put every denial, in five languages and any
position, at 0.73 or more, and every reply a turn would check that is no denial (a hedge
that it may be out of date, an offer to look it up, a package, messages or a booking it
cannot see, a quoted denial) at 0.23 or less; a draft or a translation of the user's
words scores high, and its turn is never checked. A read close to live makes the retry
search; otherwise it is offered the search and its model decides, since a search sends
words from the conversation to the web.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.chat.clock_denial import model_denies_clock
from app.modules.chat.continuation_subject import exchange_pairs
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.turn_prep import StreamContext
from app.modules.turn_reading.lesson_flow import active_lesson_step
from app.modules.turn_reading.writing import draft_followup
from app.modules.turn_reading.writing_kind import writing_request_kind
from app.services.md_fence_scan import without_fences

logger = logging.getLogger(__name__)

# Between the highest other reply a turn checks (0.23) and the lowest denial (0.73) of the
# labelled set.
_DENIES_AT = 0.4
# The reply has streamed and the turn waits for this before it finishes: the Decider's p95
# is about 0.5-0.8 s, and a check that runs out leaves the reply as it is (the hard cap).
_CHECK_SECONDS = 1.2
# The reply's opening and its end: a denial leads the answer or closes it as a note.
_HEAD_CHARS = 1500
_TAIL_CHARS = 500
_QUESTION = {
    "denies": {
        "type": "noul",
        "instructions": (
            "Does the assistant's reply say it cannot check, search, browse or see live, "
            "current or up-to-date public information (scores, rankings, prices, news, "
            "today's facts), or that it is looking something up now instead of answering? Not "
            "when what it cannot see is the user's own: their body, screen or camera, "
            "location, accounts, orders, packages, bookings, messages, files, chats or other "
            "records. Not when it only says its answer may be out of date or offers to look "
            "it up, and not when it quotes or talks about such a sentence."
        ),
    }
}


def may_check(ctx: StreamContext) -> bool:
    """Whether a denial in this turn's reply could be about public facts a search finds.
    Not small talk; not numbers a server path worked (a verified solve, a money card, a
    worked layout) or a lesson's step; not the answer to a clarify card; not a draft,
    translation or edit, whose words are the user's to send, not the reply's claims."""
    if ctx.lightweight_turn or ctx.after_card or ctx.worked is not None:
        return False
    if ctx.verified_subject is not None or ctx.money is not None:
        return False
    if active_lesson_step(ctx.recent_messages) is not None:
        return False
    content = ctx.user_message_content or ""
    if writing_request_kind(content) is not None:
        return False
    return draft_followup(content, exchange_pairs(ctx.recent_messages or [])) is None


def _quoted(question: str, reply: str) -> str:
    """The message and the reply's own prose, as the check reads them: its fences left out
    (a draft's "I can't check the live scores tonight" is the user's line, not the reply's
    claim) and a long reply's middle cut."""
    text = without_fences(reply).strip()
    if len(text) > _HEAD_CHARS + _TAIL_CHARS:
        text = f"{text[:_HEAD_CHARS]}\n…\n{text[-_TAIL_CHARS:]}"
    return f"The user's message: {question.strip()}\n\nThe assistant's reply: {text}"


async def denies_live_data(settings: Settings, question: str, reply: str) -> bool:
    """The reply says it can't get live facts ("I can't check live scores", "No puedo
    consultar datos en tiempo real", "Let me check the latest for you" and no answer).
    False when the check fails or runs out: the reply stands."""
    if not without_fences(reply).strip():
        return False
    from app.gateways.decider_gateway import decide
    from app.gateways.llm_spend import meter_reported_cost
    from app.models import model_catalog

    alias = ROUTING.decider
    try:
        answer = await decide(
            settings,
            model=model_catalog.get(alias).model.removeprefix("openrouter/"),
            state=_quoted(question, reply),
            questions=_QUESTION,
            seconds=_CHECK_SECONDS,
        )
    except Exception as exc:  # A check is a hint: without it the reply stands.
        logger.info("live denial check failed (%s)", type(exc).__name__)
        return False
    meter_reported_cost(alias, answer.usage.cost)
    denies = answer.answers.get("denies")
    return denies is not None and (denies.noul or 0.0) >= _DENIES_AT


async def asks_again(
    settings: Settings,
    ctx: StreamContext,
    calls: list[dict[str, Any]],
    accum: StreamAccum,
    written: int,
    should_cancel: Callable[[], bool] | None,
) -> bool:
    """The first call's answer, with no tool call, denies live data: ask again. A Stop
    while the check ran keeps the reply as the phone drew it."""
    if calls or accum.was_cancelled or ctx.search_sources or not may_check(ctx):
        return False
    reply = "".join(accum.parts[written:])
    question = ctx.user_message_content or ""
    # "What time is it" denied gets the clock (``finalize_text.fix_clock``).
    if model_denies_clock(reply, question):
        return False
    denied = await denies_live_data(settings, question, reply)
    if should_cancel is not None and should_cancel():
        accum.mark_user_stop()
        return False
    return denied
