"""Beside a short follow-up line: the message, and the part or step of it, the line follows.

Written from the turn's follow-up read (``chat.follow_up_read``). In a 53-turn Grade 8 chat
(2026-11-18) "explain step 2", after a water-pressure answer, explained Newton's second law
from seven turns back, and "and b?" answered half of part b: the reply had to guess which
message "step 2" and "b" belong to.
"""

from __future__ import annotations

from app.services.text_normalize import collapse_ws

_QUOTE_CHARS = 200

FOLLOW_UP_NOTE = (
    "This message follows up {where}{part}. Answer it about {target}, never about another "
    "message of this chat."
)


def _quoted(text: str) -> str:
    plain = collapse_ws(text).replace('"', "'")
    return plain if len(plain) <= _QUOTE_CHARS else f"{plain[:_QUOTE_CHARS].rstrip()}…"


def follow_up_note(
    *,
    role: str,
    text: str,
    asked: str | None,
    part: str | None,
    part_text: str | None,
) -> str:
    """The note for a line that follows up ``text`` (a message of ``role``, the answer to
    ``asked`` when it is the assistant's), at ``part`` when it names one."""
    if role == "assistant":
        where = f'your reply to "{_quoted(asked)}"' if asked else f'your message "{_quoted(text)}"'
    else:
        where = f'the earlier message "{_quoted(text)}"'
    named = ""
    if part_text:
        named = f', and asks about its part {part}: "{_quoted(part_text)}"'
    elif part:
        named = f', and asks about "{_quoted(part)}" in it'
    target = "that part of that message" if part else "that message"
    return FOLLOW_UP_NOTE.format(where=where, part=named, target=target)
