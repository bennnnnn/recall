"""A short "What?" right after a reply: the user did not follow it.

After a Spanish reply in an English app, "What?" got "Gd: good, or something else?"
(2026-10-24): the model read it as a message it could not make out and copied the example
the unclear-message rule gives. "What?", "huh?", "what do you mean", "I don't get it" right
after a reply say one thing: say it again so they follow. "What time is it?" asks something
else, and a message with no reply before it has nothing to follow.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

_MISSED = re.compile(
    r"^(?:what|wut|wat|huh|eh|hm+|pardon|sorry|come again|say (?:that|it) again|"
    r"what do you mean|what does that mean|what(?:'s| is) that|"
    r"i don'?t (?:get|understand)(?: (?:it|that|this|you))?|i'?m (?:lost|confused)|"
    r"(?:that|this) makes no sense)"
    r"[\s?!.]*$|^\?+$",
    re.IGNORECASE,
)

REPLY_MISSED_HINT = (
    "The user did not follow your last reply. Say it again so they can: simpler and shorter, "
    "the main point first. Do not ask what they meant."
)
# The words above are English: "What?" after a Spanish reply to English messages wanted
# English, and a reply told only "their latest message's language" kept the Spanish.
_IN_ENGLISH = "Write it in English, the language of their message."


def reply_missed_hint(query: str, prior: Sequence[tuple[str, str]]) -> str | None:
    """The note for "What?" and its kind right after a reply, or None."""
    replied = any(role == "assistant" and text.strip() for role, text in prior)
    if not replied or not _MISSED.match(query.strip()):
        return None
    worded = any(char.isalpha() for char in query)
    return f"{REPLY_MISSED_HINT} {_IN_ENGLISH}" if worded else REPLY_MISSED_HINT
