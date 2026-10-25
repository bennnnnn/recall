# ruff: noqa: RUF001 - the Turkish dotless i is part of language names matched below
"""The app's language, held when the user writes in it, whatever a memory says.

An English app answered "Teach me how to improve recall" in Spanish (2026-10-24): a saved
memory said "User prefers replies in Spanish". The app's language line, ranking a saved
memory last, did not hold: three replies of three stayed Spanish while the memory was in
the prompt. Reading memory facts for settings hid real ones ("User answers customer emails
in Spanish at work"), so the message is read instead, and a note beside it says to reply in
the app's language when the message is plainly written in it.

The note only ever names the app's language, so a misread message gets no note rather than
a wrong one. It is left out when the reading is unsure (one stray word: "Los Angeles
weather"; a Cyrillic name in an English line), and whenever a language is named — in the
message ("write an email in Spanish", "translate …"), earlier in the chat ("reply in
Spanish from now on", "Teach me Spanish") or in their custom instructions, in any of the
app's languages ("responde en inglés", "auf Englisch"): that choice is theirs.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.core.validation import LOCALE_NAMES, normalize_locale_code
from app.modules.todos import language_evidence
from app.services.text_normalize import straighten_apostrophes

_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")
# English words the app's other languages do not write ("was" and "will" are German, "i"
# Italian, "has" Spanish, "for" Portuguese, "me", "no", "a", "in" several).
_ENGLISH = frozenset(
    {
        "the", "is", "are", "were", "to", "of", "and", "with", "what", "how", "why", "when",
        "where", "who", "which", "my", "you", "your", "it", "this", "that", "does", "please",
        "teach", "tell", "explain", "help", "show", "give", "about", "from", "have", "not",
        "yes", "make", "want", "need", "know", "think", "should", "would", "could", "just",
        "get", "thanks", "thank", "hello", "hey", "don't", "i'm", "it's", "what's", "can't",
        "mean", "understand",
    }
)  # fmt: skip
_SCRIPTS = ("ru", "am")
_LATIN_WORDS = 2
# A language named in any app language: a choice the user made, never overridden.
_LANGUAGE_NAME = re.compile(
    r"\b(?:english|ingl[eé]s|anglais|englisch|inglese|ingil[iı]zce|spanish|espa[nñ]ol|"
    r"espagnol|spanisch|spagnolo|espanhol|[iı]spanyolca|french|fran[cç]ais|franc[eé]s|"
    r"franz[oö]sisch|francese|franc[eê]s|frans[iı]zca|german|deutsch|alem[aá]n|alem[aã]o|"
    r"allemand|tedesco|almanca|italian|italiano|italien|italienisch|[iı]talyanca|portuguese|"
    r"portugu[eêé]s|portugais|portugiesisch|portoghese|portekizce|russian|ruso|russe|russisch|"
    r"russo|rus[cç]a|turkish|t[uü]rk[cç]e|turco|turc|t[uü]rkisch|amharic|am[aá]rico|"
    r"amharique|amharisch|amarico)\b|(?:английск|русск|испанск|французск|немецк|итальянск|"
    r"португальск|турецк|амхарск)\w*|እንግሊዝኛ|አማርኛ",
    re.IGNORECASE,
)
_TRANSLATE = re.compile(r"\b(?:translat|tradu|[uü]bersetz|[cç]evir)\w*|перев[её]\w*", re.I)


def _plainly(text: str) -> str | None:
    """'en', another app language's code, or None when the message is not plainly one."""
    evidence = language_evidence(text)
    letters = sum(char.isalpha() for char in text)
    for code in _SCRIPTS:
        if evidence.get(code, 0) * 2 > letters:
            return code
    words = {word.casefold() for word in _WORD.findall(straighten_apostrophes(text))}
    english = len(words & _ENGLISH)
    latin = [(found, code) for code, found in evidence.items() if code not in _SCRIPTS]
    other, code = max(latin, default=(0, ""))
    if english > other and not any(evidence.get(script) for script in _SCRIPTS):
        return "en"
    if other >= _LATIN_WORDS and other > english:
        return code
    return None


def _names_a_language(*texts: str | None) -> bool:
    return any(isinstance(text, str) and _LANGUAGE_NAME.search(text) for text in texts)


def reply_language_hint(
    query: str, prior: Sequence[tuple[str, str]], locale: Any, instructions: Any
) -> str | None:
    """'Write this reply in English …' when the message is plainly in the app's language."""
    earlier = [text for role, text in prior if role == "user"]
    if _names_a_language(query, instructions, *earlier) or _TRANSLATE.search(query):
        return None
    app = normalize_locale_code(locale if isinstance(locale, str) else None)
    if _plainly(query) != app:
        return None
    name = LOCALE_NAMES.get(app, "English")
    return (
        f"Write this reply in {name}, the language of the user's message, whatever a saved "
        "memory or an earlier reply says."
    )
