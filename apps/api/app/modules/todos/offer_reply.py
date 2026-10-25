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

from app.modules.todos.spoken_add import SpokenAdd
from app.modules.todos.spoken_clauses import parse_spoken_adds

# "Would you like me to set up that X reminder…?", "Want me to add it to your list?",
# "Shall I remind you at 9?". The reminder is what is set, not where something goes ("add
# error handling to the reminder service") or a thing about reminders ("a to-do list app",
# "a reminder of the key steps").
_ASKS = (
    r"(?:(?:would|do) you (?:like|want) me to|want me to|shall i|should i|can i)\s+"
    r"(?:(?:go ahead and|also|quickly)\s+)?"
)
_NOT_A_REMINDER = (
    r"(?!\s+(?:lists?\s+)?(?:of|on how|about how|app|apps|system|tool|service|services|feature"
    r"|features|function|component|module|class|code|template|logic|api|screen|page)\b)"
)
# Words between the verb and the reminder, none of them a preposition: "set up that
# Practice list comprehensions reminder", not "add error handling to the reminder".
_OBJECT_WORDS = r"(?:(?!(?:to|for|in|on|of|with|from|into|about)\b)[\w'-]+\s+){0,5}?"
_OFFER = re.compile(
    rf"\b{_ASKS}(?:set(?: up)?|add|create|schedule|make|save)\s+{_OBJECT_WORDS}"
    rf"(?:reminders?|to-?dos?){_NOT_A_REMINDER}\b"
    rf"|\b{_ASKS}(?:add|put|save)\s+[^?]{{0,80}}?\s+(?:to|on|in)\s+your\s+"
    r"(?:(?:to-?do|grocery|shopping)\s+)?(?:list|to-?dos|reminders)\b(?!\s+app\b)"
    rf"|\b{_ASKS}remind you\b(?!\s+(?:how|what|why|of|that|about how)\b)"
    rf"|\b(?:would|do) you (?:like|want) (?:a|that|this)\s+reminders?\b{_NOT_A_REMINDER}",
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
    """The same, with the last reply read from the recent window (a regenerate's window
    leaves out the reply it redoes: ``turn_load.load_regenerate_turn``)."""
    for message in reversed(recent or ()):
        if getattr(message, "role", None) == "assistant":
            content = getattr(message, "content", None)
            return accepted_reminder_offer(user_text, content if isinstance(content, str) else None)
    return None


# What the offer itself names: "set up that Practice list comprehensions reminder for
# tomorrow at 7:00 PM", "remind you to call mom at 5".
_OFFERED = re.compile(
    r"\b(?:set(?: up)?|add|create|schedule|make|save)\s+(?:(?:a|an|the|that|this|your)\s+)?"
    r"(?P<title>(?:[\w'-]+\s+){1,6}?)reminders?\b(?P<when>[^?]*)",
    re.IGNORECASE,
)
_REMIND_YOU = re.compile(r"\bremind you (?P<rest>(?:to|about)\b[^?]*)", re.IGNORECASE)
_PARENS = re.compile(r"\s*\([^)]*\)")
# The user's line the offer was about: "i have a dentist appointment on thursday at 3pm".
_STATED = re.compile(
    r"^\s*(?:(?:so|well|ok|okay|hey|also)[,\s]+)?(?:i(?:'ve| have)(?: got)?|i've got|there's"
    r"|there is|i've)\s+(?:(?:a|an|the)\s+)?",
    re.IGNORECASE,
)
# "my flight is on friday at 6am" is the flight, on Friday.
_IS_WHEN = re.compile(
    r"\s+(?:is|are|was|'s)\s+(?=(?:on|at|this|next|tomorrow|today|tonight|in)\b)", re.I
)
_FIRST_CLAUSE = re.compile(r"[,;]\s+|\s+(?:but|so|and i)\s+", re.IGNORECASE)


def offered_add(offer: str, prior_user: str | None, user_timezone: str | None) -> SpokenAdd | None:
    """The reminder a yes agreed to, with its time: from the offer's own words, or else from
    the user's line before it.

    Live (2026-10-25): after "i have a dentist appointment on thursday at 3pm" and "Do you
    want me to set a reminder for you?", the model answered "yes" with "I'll set a reminder
    for you now!" and no fence, three runs in three. The server reads the reminder itself.
    """
    plain = _PARENS.sub("", offer.replace("*", ""))
    requests = []
    if found := _REMIND_YOU.search(plain):
        requests.append(f"remind me {found['rest']}")
    if found := _OFFERED.search(plain):
        requests.append(f"remind me to {found['title']}{found['when']}")
    if prior_user:
        first = _FIRST_CLAUSE.split(prior_user.strip(), maxsplit=1)[0]
        first = _IS_WHEN.sub(" ", _STATED.sub("", first))
        requests.append(f"remind me about {first}")
    for request in requests:
        adds = parse_spoken_adds(request, user_timezone=user_timezone)
        timed = [add for add in adds if add.hour is not None or add.after_minutes is not None]
        if len(adds) == 1 and timed:
            return timed[0]
    return None
