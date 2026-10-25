"""The language a reply is written in, read from the user's message.

An English app answered "Teach me how to improve recall" in Spanish (2026-10-24): a saved
memory said "User prefers replies in Spanish". The app's language line, ranking a saved
memory last, did not hold: three replies of three stayed Spanish while the memory was in
the prompt. Reading memory facts for settings hid real ones ("User answers customer emails
in Spanish at work"), so the message is read instead, and a note beside it names its
language.

No note when the message has no language of its own ("ok", "17:00", code): the chat's
language holds. None when their custom instructions name a language, or when they asked
in this chat for one ("reply in Spanish from now on"): that choice is theirs.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.core.validation import LOCALE_NAMES
from app.modules.todos import message_language
from app.services.text_normalize import straighten_apostrophes

_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")
# English words no other app language writes ("no", "me", "a", "in" are Spanish or Italian
# too).
_ENGLISH = frozenset(
    {
        "the", "is", "are", "was", "were", "to", "of", "and", "for", "with", "what", "how",
        "why", "when", "where", "who", "which", "my", "you", "your", "i", "it", "this",
        "that", "does", "please", "teach", "tell", "explain", "help", "show", "give",
        "about", "from", "have", "has", "not", "yes", "make", "want", "need", "know",
        "think", "should", "would", "could", "will", "just", "get", "thanks", "thank",
        "hello", "hey", "don't", "i'm", "it's", "what's", "can't", "mean", "understand",
    }
)  # fmt: skip
_LANGUAGE_NAMES = sorted({name.casefold() for name in LOCALE_NAMES.values()}, key=len)
_NAMES = "|".join(re.escape(name) for name in _LANGUAGE_NAMES)
# "Reply in Spanish from now on", "answer me in French", "in English please".
_ASKS_FOR_LANGUAGE = re.compile(
    rf"\b(?:repl\w*|answer\w*|respond\w*|writ\w*|speak\w*|talk\w*|chat\w*|switch\w*)\b"
    rf"[^.?!\n]{{0,30}}\b(?:in|to)\s+(?:{_NAMES})\b|\bin\s+(?:{_NAMES})\s+(?:please|from now on)\b",
    re.IGNORECASE,
)
_NAME_IN_INSTRUCTIONS = re.compile(rf"\b(?:{_NAMES}|language)\b", re.IGNORECASE)


def _message_language(text: str) -> str | None:
    """'en', another app language's code, or None when the message has no language."""
    words = {word.casefold() for word in _WORD.findall(straighten_apostrophes(text))}
    other = message_language(text)
    if other in {"ru", "am"}:  # another script: no doubt
        return other
    if words & _ENGLISH:
        return "en"
    return other


def reply_language_hint(
    query: str, prior: Sequence[tuple[str, str]], custom_instructions: str | None
) -> str | None:
    """'Write this reply in English…' for a message in a language, unless they chose one."""
    if custom_instructions and _NAME_IN_INSTRUCTIONS.search(custom_instructions):
        return None
    if any(role == "user" and _ASKS_FOR_LANGUAGE.search(text) for role, text in prior):
        return None
    code = _message_language(query)
    if code is None:
        return None
    name = LOCALE_NAMES.get(code, "English")
    return (
        f"Write this reply in {name}, the language of the user's message, whatever a saved "
        "memory or an earlier reply says."
    )
