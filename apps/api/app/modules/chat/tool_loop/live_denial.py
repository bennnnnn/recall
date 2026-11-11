"""A first answer that says it can't see live data is asked again, and this time searches.

"Perfect. totally unrelated but did the bears win today" was answered "I can't check live
scores" (live chat, 2026-10-25): the word rules read the line as a statement, so neither
the tool loop nor the reply's own call could search. Two rules that read the user's words
caught everyday statements ("went to the gym today but was too tired") in review. The
reply decides instead. When the first call carried no tool and its answer says it cannot
get live facts, the answer is taken back and the model is asked again, made to search.
The tool-loop path offers the retry only when nothing searched and the spend cap allows
tools (``StreamContext.denial_retry_tools``).

The denial was a pattern of English openings ("I can't check live …" starting a sentence
of a short reply). On a Pro phone test (2026-11-11) a five-item list said "I can't check
live rankings from here, so this list reflects widely cited reputation" mid-sentence and
went out as it was; "Let me check the current list for you" with no list after it, and
the same in Spanish or Amharic, were never caught. Perplexity's Decider now reads the
reply instead (about 0.3 s and $0.00002 a reply): on 40 labelled replies it put every
denial, in five languages and any position, at 0.65 or more, and every other reply (a
hedge that it may be out of date, an offer to look it up, "I can't see your heart rate",
talk about denials) at 0.11 or less. The retry must search, so the answer it writes has
results and does not deny again; a denial of something private (a camera, a bank
account) is not one the check reads as live.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.chat.clock_denial import model_denies_clock
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.turn_prep import StreamContext

logger = logging.getLogger(__name__)

# Between the highest other reply (0.11) and the lowest denial (0.65) of the labelled set.
_DENIES_AT = 0.4
# The reply has streamed and the turn waits for this before it finishes: the Decider's p95
# is about 0.8 s, and a check that runs out leaves the reply as it is.
_CHECK_SECONDS = 1.2
# The reply's opening and its end: a denial leads the answer or closes it as a note.
_HEAD_CHARS = 1500
_TAIL_CHARS = 500
_QUESTION = {
    "denies": {
        "type": "noul",
        "instructions": (
            "Does the assistant's reply say it cannot check, search, browse or see live, "
            "current or up-to-date information (scores, rankings, prices, news, today's "
            "facts), or that it is looking something up now instead of answering? Not when it "
            "says it cannot see something private to the user (their body, screen, accounts, "
            "files or chats), and not when it only says its answer may be out of date or "
            "offers to look it up."
        ),
    }
}


def _quoted(question: str, reply: str) -> str:
    """The message and the reply, as the check reads them: a long reply's middle left out."""
    text = reply.strip()
    if len(text) > _HEAD_CHARS + _TAIL_CHARS:
        text = f"{text[:_HEAD_CHARS]}\n…\n{text[-_TAIL_CHARS:]}"
    return f"The user's message: {question.strip()}\n\nThe assistant's reply: {text}"


async def denies_live_data(settings: Settings, question: str, reply: str) -> bool:
    """The reply says it can't get live facts ("I can't check live scores", "No puedo
    consultar datos en tiempo real", "Let me check the latest for you" and no answer).
    False when the check fails or runs out: the reply stands."""
    if not reply.strip():
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
) -> bool:
    """The first call's answer, with no tool call, denies live data: ask again. A greeting or
    thanks asks nothing live, so its reply costs no check."""
    if calls or accum.was_cancelled or ctx.search_sources or ctx.lightweight_turn:
        return False
    reply = "".join(accum.parts[written:])
    question = ctx.user_message_content or ""
    # "What time is it" denied gets the clock (``finalize_text.fix_clock``).
    if model_denies_clock(reply, question):
        return False
    return await denies_live_data(settings, question, reply)
