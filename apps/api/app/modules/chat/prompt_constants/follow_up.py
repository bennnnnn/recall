"""Beside a short follow-up line: the message, and the part or step of it, the line follows.

Written from the turn's follow-up read (``chat.follow_up_read``). In a 53-turn Grade 8 chat
(2026-11-18) "explain step 2", after a water-pressure answer, explained Newton's second law
from seven turns back, and "and b?" answered half of part b: the reply had to guess which
message "step 2" and "b" belong to.
"""

from __future__ import annotations

from app.services.text_normalize import collapse_ws

_QUOTE_CHARS = 200

# Said as what to answer about, never as what the message is: told "This message follows up
# …", a small model opened its reply with the same description of the turn (2026-11-27).
FOLLOW_UP_NOTE = (
    "Answer this message about {where}{part}, never about another message of this chat."
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
        named = f', its part {part}: "{_quoted(part_text)}"'
    elif part:
        named = f', "{_quoted(part)}" in it'
    return FOLLOW_UP_NOTE.format(where=where, part=named)
