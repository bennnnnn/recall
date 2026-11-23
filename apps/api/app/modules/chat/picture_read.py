"""A draw follow-up the Decider is unsure of: whose picture does it ask to see?

"can u show me a picture" after 7 notebooks at $2 each was read by the Decider as an
everyday painting; the text read, begun beside it, names the school problem's picture.
It is asked only in a chat that holds a school problem (``chat.school_problem``), read
from the chat's messages as stored (``raw_turns``), never the quoted, cut turns the read
sees: a long reply's answer card, or a reply that is only its picture, says so too.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from app.core.config import Settings

if TYPE_CHECKING:
    from app.modules.chat.turn_decision import TurnDecision

# The school subjects, and the pictures the app draws itself (``drawn_picture``).
_STEM = frozenset({"maths", "physics", "chemistry"})
_DRAWN = frozenset({"graph", "diagram", "molecule"})


# The messages whose problem a draw follow-up may show: the last few exchanges, uncut.
_RAW_MESSAGES = 6


def raw_turns(recent: list[Any] | None) -> list[tuple[str, str]]:
    """The chat's last messages as stored: no picture said in words, nothing cut, so a long
    reply's answer card and a reply that is only its picture still say the chat worked a
    problem (review: the quoted turns had lost both)."""
    return [
        (role, content)
        for message in (recent or [])[-_RAW_MESSAGES:]
        if (role := getattr(message, "role", None)) in {"user", "assistant"}
        and isinstance(content := getattr(message, "content", None), str)
        and content.strip()
    ]


def unsure_whose_picture(decided: dict[str, Any]) -> bool:
    """The Decider says the message asks to see what the conversation is about, but names
    no school subject, or no picture the app draws of it (a photo, a painting, none), or
    a chemistry problem's picture that is no molecule. "can u show me a picture" after 7
    notebooks at $2 each read "everyday" and a painting, after a sequence and a ticket
    problem too: 36 of the 45 picture requests of a QA round (2026-11-22) were read as a
    school problem's picture, against 45 of 45 by the text read, whose instructions say so
    (``picture_followup_eval``). Told the same in its own questions, the Decider searched
    more turns that need no search (``search_need_eval``: 0.9% to 2.4-3.7%), so it is left
    as it is and the text read, begun beside it, is asked about these alone."""
    subject, picture = decided.get("subject"), decided.get("picture")
    if decided.get("follow") != "draw":
        return False
    if subject == "chemistry":
        return picture != "molecule"
    return subject not in _STEM or picture not in _DRAWN


async def asked_of_the_text_read(
    settings: Settings,
    decision: TurnDecision,
    text_read: asyncio.Task[TurnDecision | None],
    earlier: list[tuple[str, str]],
    started: float,
) -> TurnDecision:
    """The text read's subject and picture for a draw follow-up the Decider is unsure of,
    in a chat that holds a school problem. The two are waited on together: a chat with
    none returns the Decider's read as soon as the pool says so (review)."""
    problem = asyncio.ensure_future(_after_a_problem(settings, earlier))
    text = asyncio.ensure_future(_within(settings, text_read, started))
    try:
        if not await problem:
            return decision
        return _the_problem_s_picture(decision, await text)
    finally:
        # A read stopped while it waits leaves neither running (review).
        problem.cancel()
        text.cancel()


async def _after_a_problem(settings: Settings, chat: list[tuple[str, str]]) -> bool:
    """The chat before the message holds a school problem: an everyday "show me a picture
    of it" (the Colosseum's photo, "make it blue") waits for no text read (review)."""
    from app.modules.chat.school_problem import chat_holds_a_school_problem

    lines = [content for role, content in chat if role == "user"]
    replies = [content for role, content in chat if role == "assistant"]
    return await chat_holds_a_school_problem(settings, lines, replies)


async def _within(
    settings: Settings, text_read: asyncio.Task[TurnDecision | None], started: float
) -> TurnDecision | None:
    """The text read, within the read's own budget (p50 1.1 s, p95 1.7 s). Capped at the
    reply's shorter wait (review, 2026-11-22), the eval's bad replies went from 5 to 11 of
    45: the Decider's "everyday" stood, and the reply asked "Sure — what do you want a
    picture of?". The prep waits as long for a line that may ask to see the problem
    (``figure_turn.read_shows_it``), so neither gives up on it first."""
    left = settings.live_read_timeout_seconds - (time.monotonic() - started)
    try:
        read = await asyncio.wait_for(text_read, max(0.0, left))
    except TimeoutError:
        return None
    return read


def _the_problem_s_picture(read: TurnDecision, text: TurnDecision | None) -> TurnDecision:
    """The Decider's read with the text read's subject and picture, when the text read
    says the message asks to see a school problem's picture; else the Decider's alone."""
    if text is None or text.follow != "draw" or text.subject not in _STEM:
        return read
    return type(read).model_validate(
        {**read.model_dump(), "subject": text.subject, "picture": text.picture}
    )
