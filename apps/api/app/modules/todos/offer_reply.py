"""A yes to the last reply's offer to set a reminder is that request.

Live (2026-10-25): the reply ended "Would you like me to set up that **Practice list
comprehensions** reminder for tomorrow (Monday) at 7:00 PM?" and the user said "yes". The
turn read "yes" alone: no To-do instructions reached the model, which wrote "Setting that
reminder for you now!" with no card, and nothing was saved. A short yes right after a
reply whose last question offers a reminder now loads the To-do block like the request
it answers, and the offer's own day and clock count as said: the user agreed to them.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

# "Would you like me to set up that X reminder…?", "Want me to add it to your list?",
# "Shall I remind you at 9?". "Would you like a reminder app recommendation?" offers none.
_OFFER = re.compile(
    r"\b(?:(?:would|do) you (?:like|want) me to|want me to|shall i|should i|can i|"
    r"(?:would|do) you want (?:a|that|this)|(?:would|do) you like (?:a|that|this))\s+"
    r"(?:(?:go ahead and|also|quickly)\s+)?"
    r"(?:(?:set(?: up)?|add|create|schedule|make|save|put)\b[^?]{0,120}?"
    r"\b(?:reminders?|to-?dos?|your (?:to-?do )?list)\b(?!\s+(?:app|apps|system|tool)\b)"
    r"|remind you\b(?!\s+(?:how|what|why|of|that)\b)|reminders?\b(?!\s+(?:app|apps|system|tool)\b))",
    re.IGNORECASE,
)
# The reply's sentences that ask; the offer is the last one, near the end.
_QUESTION = re.compile(r"[^.!?\n]*\?")
_TAIL_CHARS = 240


def accepted_reminder_offer(user_text: str | None, prior_assistant: str | None) -> str | None:
    """The offer ``user_text`` says yes to, or None.

    Only a bare yes counts ("yes", "sure", "go ahead"): "yes but make it 8" changes
    the offer and is read as its own words.
    """
    from app.modules.chat import is_short_confirmation

    if not user_text or not prior_assistant or not is_short_confirmation(user_text):
        return None
    tail = prior_assistant.rstrip()[-_TAIL_CHARS:]
    questions = _QUESTION.findall(tail)
    if not questions:
        return None
    offer = questions[-1].strip().replace("*", "")
    return offer if _OFFER.search(offer) else None


def accepted_offer_in(user_text: str | None, recent: Sequence[Any] | None) -> str | None:
    """The same, with the last reply read from the recent window."""
    for message in reversed(recent or ()):
        if getattr(message, "role", None) == "assistant":
            content = getattr(message, "content", None)
            return accepted_reminder_offer(user_text, content if isinstance(content, str) else None)
    return None
