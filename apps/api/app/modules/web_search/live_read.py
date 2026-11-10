"""Whether a message's answer depends on facts that change: a model reads it, not word rules.

The reply's own model decides most searches (``chat.tool_loop.reply_calls``), but it
answers what changed since it was trained from memory: offered the tool, the free model
said "Argentina won the last World Cup" in November 2026 and searched "who won the last
world cup" in none of three runs. One short call to a fast model reads each message
beside the turn's prep, while history and memory load, and answers one question: does the
answer depend on facts that may have changed, or that a model cannot know as of today?
Yes, or the user asked for a search, and the read's own query is searched before the
reply's call, which then answers from the results in one call. No, and the reply's call
carries no search tool: the read is the one decider (``chat.tool_loop.reply_calls``). No
answer in time, and the reply's model holds the tool and decides. Nothing here raises into
a turn.

In one chat about a hot MacBook Air (2026-11-09) the read saw only the reply before the
message, sent to it as a chat turn: it answered "Can i just buy another one" by searching
"iPhone 16 price", and "How much" (the battery) as an iPhone battery's cost. It now sees
the last two exchanges, quoted in one message, so it judges the message instead of carrying
on the chat; and the settled kinds it searched there are named in its instructions: a
choice between repairing and buying, a how-to on a device, where the user is, and getting
to a place the chat already named, which the reply answers with a map link.
``tests/behavior/search_need_eval.py`` measures it on ``search_need_corpus.json``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models.routing_lanes import ROUTING

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 1200
# Each earlier message the read sees, and how many: the last two exchanges.
_EARLIER_CHARS = 400
_EARLIER_MESSAGES = 4

_SYSTEM = (
    "Today is {today}. Decide whether the reply to the user's last message must look "
    "something up on the web first.\n\n"
    "live is true only when the answer needs facts that change, or that a model trained in "
    "the past cannot know as of today:\n"
    "- news and events, results and scores, the latest or the next of anything, whether "
    "something is out yet\n"
    "- who holds an office or a title now\n"
    "- prices, costs and rates; weather; schedules and opening hours\n"
    "- a person or a product in the news\n"
    "- places to find near the user (the nearest shop, a restaurant, what is open)\n\n"
    "live is false for everything else, even when the conversation before it was about "
    "something live:\n"
    "- greetings, small talk and thanks; the user's own life, plans and feelings\n"
    "- advice and choices: whether to repair, replace or buy something, what to do, which "
    "to pick\n"
    "- how things work and how to do something: steps, settings and checks on a phone, "
    "computer or app (unless it names a model or version that may be newer than you "
    "know); who makes or repairs something\n"
    "- maths, science, writing, code, history and other settled knowledge\n"
    "- where the user is: the app knows their place\n"
    "- what the user told you or keeps here: their earlier chats, memory, notes, to-dos "
    "and files, even when they ask you to search or look them up\n"
    "- getting from the user to a place the conversation already named, on foot, by car, "
    "bike, bus or train (can they walk, how to get there, how long, how far): the reply "
    "answers with a map link, which shows the route, its time and the next bus or train; "
    "never a web search\n"
    "- work on the conversation itself: a summary of it, another practice problem, "
    "explaining something again, a shorter version\n\n"
    "Earlier turns, when given, show what the last message refers to; decide for the last "
    "message.\n\n"
    "Reply with JSON only, three keys in this order: asked is true when the user's last "
    "message asks you to search the web or look up something about the world (a fact, a "
    "person, a place, a thing), google it or check online, whatever the topic; a search of "
    "their own chats, memory, notes, to-dos or files is not asked (the app holds those), "
    "and otherwise asked is false; query is what a person would type into a search engine to "
    "answer the message, standing alone (spell out who or what the conversation is about: "
    "a full name, a product's model, a place), in the message's language, with no month or "
    'year unless the message names one, or "" when live and asked are both false. '
    'Example: {{"asked": false, "query": "World Cup winner", "live": true}}.'
)


class LiveRead(BaseModel):
    # The user asked for a search of the web ("google it", "can you look up …"). Told only
    # that such a message is live, the read still called "who invented the telephone"
    # settled. A search of their own chats or memory is not one: its words would go to the
    # web, and ``recall_chats`` is what they meant.
    asked: bool = False
    query: str = Field(default="", max_length=200)
    live: bool

    @property
    def searches(self) -> bool:
        """The turn searches before the reply: its answer is live, or the user asked."""
        return self.live or self.asked


def earlier_turns(recent: list[Any] | None) -> list[tuple[str, str]]:
    """The last exchanges of an oldest-first window, as the read sees them: what a short
    follow-up ("How much", "Can I walk?") refers to."""
    turns = [
        (role, content[:_EARLIER_CHARS])
        for message in recent or []
        if (role := getattr(message, "role", None)) in {"user", "assistant"}
        and isinstance(content := getattr(message, "content", None), str)
        and content.strip()
    ]
    return turns[-_EARLIER_MESSAGES:]


def _messages(text: str, earlier: list[tuple[str, str]]) -> list[dict[str, str]]:
    """The instructions, and one message to judge. The earlier turns are quoted in it, not
    sent as turns: given them as the chat, a model answered the user instead of judging."""
    today = datetime.now(UTC).strftime("%B %Y")
    quoted = "\n".join(
        f"{'User' if role == 'user' else 'Assistant'}: {content}" for role, content in earlier
    )
    last = f"The user's last message: {text[:_MAX_INPUT_CHARS]}"
    return [
        {"role": "system", "content": _SYSTEM.format(today=today)},
        {"role": "user", "content": f"Earlier turns:\n{quoted}\n\n{last}" if quoted else last},
    ]


async def read_live(
    settings: Settings, text: str, *, earlier: list[tuple[str, str]]
) -> LiveRead | None:
    """Whether the answer depends on facts that change, and its query; None: no read."""
    question = text.strip()
    if not question:
        return None
    # Imported here: SymPy pool workers import this package, not the gateway.
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        # Past the day's spend cap, or with it unreadable, nothing is read: the reply's
        # model still decides.
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return None
        read = await complete_structured(
            settings=settings,
            model_alias=ROUTING.live_read,
            messages=_messages(question, earlier),
            schema=LiveRead,
            max_tokens=80,
            timeout_seconds=settings.live_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure leaves the turn to the model.
        logger.info("live read failed (%s)", type(exc).__name__)
        return None
    return read


def start_live_read(
    settings: Settings, text: str, *, recent: list[Any] | None
) -> asyncio.Task[LiveRead | None] | None:
    """The read, started now so it runs beside the turn's prep; None when search is off.
    ``recent``: the chat's window before this message, oldest first."""
    if not (
        settings.live_read_enabled
        and settings.web_search_enabled
        and settings.reply_search_tool_enabled
        and settings.mcp_tool_loop_enabled
    ):
        return None
    return asyncio.create_task(read_live(settings, text, earlier=earlier_turns(recent)))


async def live_read_result(
    task: asyncio.Task[LiveRead | None] | None, settings: Settings
) -> LiveRead | None:
    """The read, when it answered within ``live_read_wait_seconds`` of the reply asking:
    the reply waits no longer than that for it, whatever the read's own timeout."""
    if task is None:
        return None
    try:
        read = await asyncio.wait_for(task, settings.live_read_wait_seconds)
    except TimeoutError:
        return None
    return read
