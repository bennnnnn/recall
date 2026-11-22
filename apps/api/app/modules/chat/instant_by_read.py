"""An instant reply the turn's read says the message did not ask for gives way to the model.

Two instant replies are decided by word rules before the read is in:

- "I don't have your location yet…", for a message the location rules call nearby. In 100
  everyday chats (QA, 2026-11-22) it answered "you think it means I am sad?" after a dream,
  "where do i find the table of contents" and "can i just check bestbuy.com", word for word.
  It stays only when the read says the answer needs facts that change (a place near them,
  today's weather): the read's ``live``.
- A subject's verified reply for a message the read says asks the last answer explained or
  carried on ("explain it simpler pls", "go on"): the same working again is no explanation.

The read is waited for at most ``live_read_wait_seconds``; with no read the instant reply
stands, as before.
"""

from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.chat.turn_trace import note_prompt_rule
from app.modules.web_search import LOCATION_ASK_OPENING

# The read's kinds that ask the last answer talked through, never worked again.
TALKED_THROUGH = frozenset({"explain", "more"})


async def instant_reply_by_read(ctx: StreamContext, settings: Settings) -> None:
    """Drop an instant reply the read says the message did not ask for (module docstring)."""
    reply = ctx.instant_reply
    task = ctx.live_read
    if not reply or task is None or task.cancelled():
        return
    location_ask = reply.startswith(LOCATION_ASK_OPENING)
    if not location_ask and ctx.verified_subject is None:
        return
    if not task.done():
        await asyncio.wait([task], timeout=settings.live_read_wait_seconds)
    if not task.done() or task.cancelled() or task.exception() is not None:
        return
    read = task.result()
    if read is None:
        return
    if location_ask and not read.searches:
        ctx.instant_reply = None
        note_prompt_rule("read.no_location_needed")
    elif not location_ask and read.follow in TALKED_THROUGH:
        ctx.instant_reply = None
        note_prompt_rule("read.explain_not_instant")
