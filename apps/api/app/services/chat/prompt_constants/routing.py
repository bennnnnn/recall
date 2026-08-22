"""Turn classifiers used to pick prompt hints and context load."""

import re

from app.services import time_context as time_context_service
from app.services.text_normalize import collapse_ws

# Patterns assume input was passed through ``collapse_ws`` (single spaces only).
_BROAD_SELF_QUESTION = re.compile(
    r"^(?:"
    r"who am i\??"
    r"|tell me about me\??"
    r"|what do you know about me\??"
    r"|describe me\??"
    r"|what(?:'re| are) i like\??"
    r")[.!?]*$",
    re.IGNORECASE,
)


def is_broad_self_question(text: str) -> bool:
    """Broad identity questions — name only, no personal context dump."""
    cleaned = collapse_ws(text)
    if not cleaned or time_context_service.is_location_question(cleaned):
        return False
    return bool(_BROAD_SELF_QUESTION.match(cleaned))


_LIGHTWEIGHT_TURN = re.compile(
    r"^(?:"
    r"hi|hello|hey|hiya|yo|sup"
    r"|thanks|thank you|thx|ty"
    r"|ok|okay|k|cool|nice|great|perfect|awesome"
    r"|got it|sounds good|makes sense|understood"
    r"|yes|no|yep|nope|sure|bye|goodbye|cya|see ya"
    r"|lol|lmao|haha|hehe"
    r")(?:[!?.…, ]+(?:thanks|thank you|thx))?[!?.… ]*$",
    re.IGNORECASE,
)


def is_lightweight_chat_turn(text: str, *, active_vocab_turn: bool = False) -> bool:
    """Ultra-brief social turns (hi / thanks / ok) — short reply style only.

    Memory / status theater is gated separately by ``needs_rich_context`` so we
    do not grow this allowlist for every casual phrase ("how is ur day", etc.).
    """
    if active_vocab_turn:
        return False
    cleaned = collapse_ws(text)
    if not cleaned:
        return True
    if len(cleaned) <= 2 and cleaned.isalpha():
        return True
    if len(cleaned) <= 24 and _LIGHTWEIGHT_TURN.match(cleaned):
        return True
    return False


# Opt-in cues for loading memory / todos / projects / "remembering…" status.
# Default is fast (no personal context) — do not grow a greeting allowlist.
_PERSONAL_CONTEXT_CUE = re.compile(
    r"(?:"
    r"\b(?:"
    r"remember|recall|you (?:know|remember)|what do you know|"
    r"don'?t forget|keep in mind|"
    r"we (?:talked|discussed|decided)|last time|"
    r"earlier (?:you|we)|from (?:my|our) (?:last|previous)"
    r")\b|"
    r"\b(?:about me|tell me about (?:me|myself))\b|"
    r"\bmy\s+(?:"
    r"name|email|preference|preferences|diet|routine|schedule|"
    r"calendar|wife|husband|kids?|dog|cat|job|work|boss|team|"
    r"project|projects|todo|todos|list|lists|reminder|reminders|"
    r"allerg(?:y|ies)|favorite|usual|memory|memories|"
    r"vocab(?:ulary)?|words?|learning"
    r")\b"
    r")",
    re.IGNORECASE,
)

# Progress / "what did I learn" — not dictionary lookups like "another word for".
_LEARNING_PROGRESS_CUE = re.compile(
    r"(?:"
    r"\bvocab(?:ulary)?\b|"
    r"\b(?:what|which) words?\b|"
    r"\bwords? (?:did|have) i\b|"
    r"\b(?:learn(?:ed|ing)?|studied|practiced|mastered) today\b|"
    r"\btoday'?s (?:words?|vocab(?:ulary)?|lesson|quiz)\b|"
    r"\bmy (?:vocab(?:ulary)?|words|learning)\b|"
    r"\blearning (?:class|progress|path|topic)s?\b|"
    r"\bhow many words\b|"
    r"\bwords? (?:i|have i) (?:learn|learned|studied|mastered)\b"
    r")",
    re.IGNORECASE,
)


def is_learning_progress_question(text: str) -> bool:
    """True when the user is asking about their Recall Learning words/progress."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    return bool(_LEARNING_PROGRESS_CUE.search(cleaned))


def needs_rich_context(
    text: str,
    *,
    active_vocab_turn: bool = False,
    day_planning: bool = False,
    day_reflection: bool = False,
) -> bool:
    """True when this turn should load personal context (memory/todos/projects).

    Systemic default: casual chat is slim. Opt in via personal/retrieval cues,
    day-planning, or vocab turns — not via an ever-growing greeting list.
    Callers may OR in calendar/email/todo classifiers from ``turn_prep.mode``.
    """
    if active_vocab_turn or day_planning or day_reflection:
        return True
    if is_lightweight_chat_turn(text, active_vocab_turn=active_vocab_turn):
        return False
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    if is_broad_self_question(cleaned):
        return True
    if is_writing_deliverable_request(cleaned):
        return True
    if is_learning_progress_question(cleaned):
        return True
    return bool(_PERSONAL_CONTEXT_CUE.search(cleaned))


LIGHTWEIGHT_REPLY_HINT = (
    "This is a short social turn (greeting / ack). Reply in one brief sentence. "
    "Do not dig into memory, lists, calendar, or projects unless the user asked."
)

_WRITING_DELIVERABLE = re.compile(
    r"\b("
    r"send (?:me )?(?:an? )?email|"
    r"email (?:to|my)|"
    r"write (?:me )?(?:an? )?email|"
    r"draft (?:an? )?email|"
    r"compose (?:an? )?email|"
    r"send (?:a )?(?:text|message)|"
    r"text (?:to|my)|"
    r"message (?:to|my)"
    r")\b",
    re.IGNORECASE,
)


def is_writing_deliverable_request(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_WRITING_DELIVERABLE.search(cleaned))
