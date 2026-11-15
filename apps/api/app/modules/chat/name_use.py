"""The user's name now and then, not in every reply.

In the owner's Greeting chat (2026-11-15) "bini" was in 94 of 100 replies, each line of an
emergency included ("Bini, call 911 now"). The profile says to use the name rarely
(``prompt_profile``), and the free plan's model followed the chat before it: once a reply
named them, the next did. So when one of the last two replies already called the user by
name, this one does not: the name goes from where it addresses them ("Bini, …", "…, bini!",
"Hey bini!"). A name in a sentence about them ("Bini is a great name"), a draft's sign-off
and anything in a fence stay.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.models.orm import User
from app.modules.chat.markdown_regions import map_prose_outside_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# The replies looked back on: the name at most once in three replies.
_LOOK_BACK = 2


def _patterns(name: str) -> tuple[re.Pattern[str], ...]:
    n = re.escape(name)
    return (
        # "…, bini!", "Sorry, bini, that's fair", "**A is correct, bini!**".
        re.compile(rf",[ \t]*{n}\b(?=[ \t]*(?:[,.!?;:)\u2014\u2013*]|$))", re.IGNORECASE | re.M),
        # "Bini, call 911" at a sentence's start: the next word takes the capital ("Bini, \"To
        # eat\" is …" keeps its quote).
        re.compile(
            rf"(?P<start>^|(?<=[.!?])[ \t]+|\*\*)(?P<name>{n}),[ \t]+(?P<next>[^\s*])",
            re.IGNORECASE | re.M,
        ),
        # "Hey bini!": one word, then the name, then the sentence's mark.
        re.compile(
            rf"(?P<start>^|(?<=[.!?])[ \t]+)(?P<word>[^\W\d_]+)[ \t]+{n}(?=[!.,?])",
            re.IGNORECASE | re.M,
        ),
    )


def without_name(text: str, name: str) -> str:
    """``text`` with ``name`` gone from where it addresses the reader, outside fences."""
    by_comma, leading, greeting = _patterns(name)

    def rewrite(prose: str) -> str:
        prose = by_comma.sub("", prose)
        prose = leading.sub(lambda m: f"{m['start']}{m['next'].upper()}", prose)
        return greeting.sub(lambda m: f"{m['start']}{m['word']}", prose)

    return map_prose_outside_fences(text, rewrite)


def named_lately(name: str, recent: Sequence[Any]) -> bool:
    """One of the last ``_LOOK_BACK`` replies called the user by ``name``."""
    word = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
    replies = [
        content
        for message in reversed(recent)
        if getattr(message, "role", None) == "assistant"
        and isinstance(content := getattr(message, "content", None), str)
    ][:_LOOK_BACK]
    return any(word.search(reply) for reply in replies)


def first_name(user: User | None) -> str | None:
    name = ((user.name if user is not None else None) or "").strip().split()
    return name[0] if name and len(name[0]) >= 2 else None


def spare_name_pass(state: FinalizeState) -> str:
    """The finalize pass: no name in a reply when one of the last two used it."""
    name = first_name(state.ctx.user)
    if state.server_text or name is None:
        return state.text
    if not named_lately(name, state.ctx.recent_messages or []):
        return state.text
    return without_name(state.text, name)
