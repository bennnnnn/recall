"""Whether a message's answer depends on facts that change: a model reads it, not word rules.

The reply's own model decides most searches (``chat.tool_loop.reply_calls``), but it
answers what changed since it was trained from memory: offered the tool, the free model
said "Argentina won the last World Cup" in November 2026 and searched "who won the last
world cup" in none of three runs. One short call to a fast model reads each message
beside the turn's prep, while history and memory load, and answers one question: does the
answer depend on facts that may have changed, or that a model cannot know as of today?
Yes, and the read's own query is searched before the reply's call, which then answers
from the results in one call. No, or no answer in time, and the reply's model still holds
the tool. Nothing here raises into a turn.
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
_EARLIER_CHARS = 300

_SYSTEM = (
    "Today is {today}. Decide whether a good answer to the user's last message needs facts "
    "that change, or that a model trained in the past cannot know as of today: news and "
    "events, results and scores, the latest or the next of anything, whether something is "
    "out yet, who holds an office or a title now, prices and rates, weather, schedules and "
    "opening hours, a person or a product in the news. live is false for greetings and "
    "small talk, the user's own life and feelings, maths and science problems, writing, "
    "code, advice, how things work, history and other settled knowledge, and work on the "
    "conversation itself (a summary of it, another practice problem, explaining something "
    'again). Reply with JSON only: {{"live": true}} or {{"live": false}}.'
)


class LiveRead(BaseModel):
    live: bool
    query: str = Field(default="", max_length=200)


def _messages(text: str, earlier: str | None) -> list[dict[str, str]]:
    today = datetime.now(UTC).strftime("%B %Y")
    messages = [{"role": "system", "content": _SYSTEM.format(today=today)}]
    if earlier:
        # A follow-up ("and who won in ohio?") is read with the reply it follows.
        messages.append({"role": "assistant", "content": earlier[:_EARLIER_CHARS]})
    messages.append({"role": "user", "content": text[:_MAX_INPUT_CHARS]})
    return messages


async def read_live(settings: Settings, text: str, *, earlier: str | None) -> LiveRead | None:
    """Whether the answer depends on facts that change, and its query; None: no read."""
    question = text.strip()
    if not question:
        return None
    # Imported here: SymPy pool workers import this package, not the gateway.
    from app.gateways.structured_completion import complete_structured

    try:
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


def last_reply(messages: list[Any] | None) -> str | None:
    """The newest assistant reply in an oldest-first window: the read's context."""
    for message in reversed(messages or []):
        if getattr(message, "role", None) == "assistant":
            content = getattr(message, "content", None)
            return content if isinstance(content, str) else None
    return None


def start_live_read(
    settings: Settings, text: str, *, earlier: str | None
) -> asyncio.Task[LiveRead | None] | None:
    """The read, started now so it runs beside the turn's prep; None when search is off."""
    if not (
        settings.live_read_enabled
        and settings.web_search_enabled
        and settings.reply_search_tool_enabled
        and settings.mcp_tool_loop_enabled
    ):
        return None
    return asyncio.create_task(read_live(settings, text, earlier=earlier))


async def live_read_result(
    task: asyncio.Task[LiveRead | None] | None, settings: Settings
) -> LiveRead | None:
    """The read, when it said live within ``live_read_wait_seconds`` of the reply asking:
    the reply waits no longer than that for it, whatever the read's own timeout."""
    if task is None:
        return None
    try:
        read = await asyncio.wait_for(task, settings.live_read_wait_seconds)
    except TimeoutError:
        return None
    return read if read is not None and read.live else None
