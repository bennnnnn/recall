"""A verified instant reply that answers part of what the message asks gives way to the model's.

"An ambulance siren emits 700 Hz ... What frequency does a stationary listener hear as it
approaches, and as it moves away?" got the approach's 767 Hz, verified, as the whole reply,
and "Find the angle of the first-order maximum and the highest order that can be seen" the
angle alone (live round, 2026-11-21): the subject's word rules counted one ask in each, so
the solver's one result went out instantly and the model never saw the question. The turn's
read counts the separate results a message asks for (``decider_read.ASKS_QUESTION``), in any
wording or language; when it counts more than the verified block answers, the subject marks
the block partial and gives the rule its reply writes the rest by
(``SubjectAdapter.answers_part``), and the model writes around the same checked card.

The read decides, never a word: a message whose asking sentences join more than one thing
(``_may_ask_more``) waits for it up to ``live_read_wait_seconds``; a read later than that
keeps the instant reply, which may lose a part, never the card; any other message never
waits, and the word rules (each subject's own count) stay the fallback.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_trace import note_prompt_rule
from app.services.subjects.registry import subject_adapter

if TYPE_CHECKING:
    from app.modules.chat.turn_prep.context import StreamContext

# A sentence, a decimal point kept inside it.
_SENTENCE = re.compile(r"(?:[^.?!\n]|(?<=\d)\.(?=\d))+[.?!]*")
# A sentence that asks: it ends on "?" or holds an order or a question word.
_ASKING = re.compile(
    r"\?\s*$|\b(?:find|calculate|compute|determine|work\s+out|estimate|evaluate|state|give|"
    r"what|which|how|when|where|why)\b",
    re.IGNORECASE,
)
# What joins a second ask to the first: "and", a comma, "also", "both", "each", "then".
_JOINS = re.compile(r"[,;:]|\b(?:and|also|both|each|then|plus|as\s+well\s+as|or)\b", re.I)


def _may_ask_more(text: str) -> bool:
    """The message's asking sentences may ask for more than one thing: two of them, or one
    that joins something to its ask. Only then is the read worth waiting for. A message
    none of whose sentences these words read as asking ("Calcula su aceleración y la
    distancia") is in words they do not know: the read decides it (review, #2525)."""
    asking = [s.group() for s in _SENTENCE.finditer(text) if _ASKING.search(s.group())]
    if not asking:
        return True
    return len(asking) > 1 or any(_JOINS.search(sentence) for sentence in asking)


async def write_the_rest(ctx: StreamContext, settings: Settings) -> None:
    """Drop a verified instant reply the read says answers fewer results than the message
    asks for, the block marked partial and the reply told to answer the rest (the module
    docstring)."""
    verified = ctx.verified_subject
    if ctx.instant_reply is None or verified is None or verified.subject is None:
        return
    text = ctx.user_message_content or ""
    task = ctx.live_read
    # A read already in is always used; only waiting for one is gated on the words.
    if task is None or task.cancelled() or (not task.done() and not _may_ask_more(text)):
        return
    if not task.done():
        await asyncio.wait([task], timeout=settings.live_read_wait_seconds)
    if not task.done() or task.cancelled() or task.exception() is not None:
        note_prompt_rule("subject.asks_read_late")
        return
    read = task.result()
    if read is None or read.asks is None:
        return
    adapter = subject_adapter(verified.subject)
    partial = adapter.answers_part(verified, read.asks)
    if partial is None:
        return
    block, rule = partial
    ctx.instant_reply = None
    ctx.verified_subject = block
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, rule)
    note_prompt_rule(f"{verified.subject}.partial_by_read")
