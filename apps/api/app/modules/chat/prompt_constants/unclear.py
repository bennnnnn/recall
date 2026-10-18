"""A lone word or two whose meaning is unclear: notice it, don't greet past it.

"Bo" got "Hey Bini! How's it going?", as if it were "hi". A person reacts to the
word itself: "Bo? Did you mean something in Amharic, or were you still typing?"
A clear word ("photosynthesis", "Paris") is still answered as usual.
"""

from __future__ import annotations

import re
from typing import Any

from app.modules.chat.prompt_constants.routing import (
    is_lightweight_chat_turn,
    is_short_reply,
    prior_looks_like_offer,
)
from app.services.text_normalize import collapse_ws

# One or two words of letters: no numbers, maths, links or sentences.
_ONE_OR_TWO_WORDS = re.compile(r"^[^\W\d_]{1,14}(?:\s+[^\W\d_]{1,14})?[?!.…]*$")

UNCLEAR_SHORT_TURN_HINT = (
    "The user sent only a word or two. If the meaning is clear (a topic, a name, a word to "
    "define), answer it as usual. If it is not (a typo, a word from another language, a "
    "message cut off mid-typing), do not treat it as a greeting: react to the word itself and "
    "make one natural guess at what they meant (its meaning in a language they may speak, or "
    "that they were still typing), in one or two short, warm lines, the way a person would."
)


def _last_assistant_text(exchange: list[Any] | None) -> str | None:
    for message in reversed(exchange or []):
        if getattr(message, "role", None) == "assistant":
            content = getattr(message, "content", None)
            return content if isinstance(content, str) else None
    return None


def is_unclear_short_turn(text: str | None, exchange: list[Any] | None = None) -> bool:
    """True for "Bo": a word or two that is not hi / ok / yes and answers no question."""
    cleaned = collapse_ws(text or "")
    if not _ONE_OR_TWO_WORDS.match(cleaned):
        return False
    if is_lightweight_chat_turn(cleaned) or is_short_reply(cleaned):
        return False
    # "Paris" after "Where should we go?" answers it.
    return not prior_looks_like_offer(_last_assistant_text(exchange))
