# ruff: noqa: RUF001
"""Whether a message asks what the app can do, or names one of its settings."""

from __future__ import annotations

import unicodedata

from app.core.validation import unify_devanagari
from app.modules.turn_reading.writing_kind import writing_request_kind
from app.services.text_normalize import collapse_ws

_SETTING_WORDS = frozenset(
    {
        "model",
        "models",
        "tone",
        "emoji",
        "emojis",
        "language",
        "memory",
        "voice",
        "notifications",
        "setting",
        "settings",
        "default",
    }
)


def names_a_setting(text: str | None) -> bool:
    """True when ``text`` uses a word for one of the app's settings."""
    words = {word.strip(".,!?;:'\"").lower() for word in (text or "").split()}
    return bool(words & _SETTING_WORDS)


# Home-chip prompts (the app's languages) plus short paraphrases.
_CAPABILITIES_EXACT = (
    "what can you help me with? give a few concrete examples.",
    "what can you do?",
    "what can you do",
    "en qué puedes ayudarme? dame algunos ejemplos concretos.",
    "qué puedes hacer?",
    "en quoi peux-tu m'aider ? donne quelques exemples concrets.",
    "que peux-tu faire ?",
    "no que você pode me ajudar? dê alguns exemplos concretos.",
    "o que você pode fazer?",
    "чем ты можешь помочь? приведи несколько конкретных примеров.",
    "что ты умеешь?",
    "bana nasıl yardımcı olabilirsin? birkaç somut örnek ver.",
    "ne yapabilirsin?",
    "በምን ልረዳኝ ትችላለህ? ጥቂት ተጨባጭ ምሳሌዎችን ንገረኝ።",
    "ምን ማድረግ ትችላለህ?",
    "आप किन चीज़ों में मेरी मदद कर सकते हैं? कुछ ठोस उदाहरण दीजिए।",
    "आप क्या कर सकते हैं?",
)


# Stems must sit near the start. Remainder after the stem is checked for a
# real task ("python", "this bug") vs an examples-ask / filler.
_CAPABILITIES_STEMS = (
    "what can you help me with",
    "what can you do",
    "how can you help me",
    "how can you help",
    "what do you help with",
    "what are you capable of",
    "what are your capabilities",
    "tell me what you can do",
    "what are you good at",
    "en qué puedes ayudarme",
    "en que puedes ayudarme",
    "qué puedes hacer",
    "que puedes hacer",
    "en quoi peux-tu m'aider",
    "que peux-tu faire",
    "no que você pode me ajudar",
    "no que voce pode me ajudar",
    "o que você pode fazer",
    "o que voce pode fazer",
    "чем ты можешь помочь",
    "что ты умеешь",
    "bana nasıl yardımcı olabilirsin",
    "bana nasil yardimci olabilirsin",
    "ne yapabilirsin",
    "በምን ልረዳኝ ትችላለህ",
    "ምን ማድረግ ትችላለህ",
    "आप किन चीज़ों में मेरी मदद कर सकते हैं",
    "आप मेरी क्या मदद कर सकते हैं",
    "आप मेरी कैसे मदद कर सकते हैं",
    "आप क्या कर सकते हैं",
    "आप क्या कर सकते हो",
    "तुम क्या कर सकते हो",
    "तुम क्या कर सकती हो",
)


_EXAMPLE_TAILS = (
    "give a few concrete examples",
    "give some concrete examples",
    "give a few examples",
    "give some examples",
    "dame algunos ejemplos concretos",
    "dame algunos ejemplos",
    "donne quelques exemples concrets",
    "donne quelques exemples",
    "dê alguns exemplos concretos",
    "de alguns exemplos concretos",
    "dê alguns exemplos",
    "приведи несколько конкретных примеров",
    "приведи несколько примеров",
    "birkaç somut örnek ver",
    "birkac somut ornek ver",
    "birkaç örnek ver",
    "ጥቂት ተጨባጭ ምሳሌዎችን ንገረኝ",
    "कुछ ठोस उदाहरण दीजिए",
    "कुछ उदाहरण दीजिए",
    "कुछ उदाहरण दो",
)


_FILLER_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "me",
        "my",
        "please",
        "today",
        "now",
        "just",
        "really",
        "for",
        "to",
        "with",
        "about",
        "hey",
        "hi",
        "hello",
        "recall",
        "por",
        "favor",
        "s'il",
        "vous",
        "plait",
        "lütfen",
        "lutfen",
        "कृपया",
        "प्लीज़",
        "आज",
        "अभी",
    }
)


_MAX_CAPABILITIES_CHARS = 240


_STEM_MAX_START = 40


def _is_mark(char: str) -> bool:
    """A Devanagari vowel sign or virama. Not an emoji's variation selector or keycap
    ("❤️", "1️⃣"), which are marks too and would stand as words of their own."""
    return "\u0900" <= char <= "\u097f" and unicodedata.category(char).startswith("M")


def _fold_capabilities_text(text: str) -> str:
    cleaned = collapse_ws(unify_devanagari(text)).replace("\u2019", "'").replace("¿", "")
    return cleaned.casefold()


def _letters_and_spaces(text: str) -> str:
    """Replace punctuation with spaces in one pass (no regex). A Devanagari vowel sign or
    virama is part of its word, not punctuation."""
    chars: list[str] = []
    for char in text:
        if char.isalnum() or char.isspace() or char in {"'", "-"} or _is_mark(char):
            chars.append(char)
        else:
            chars.append(" ")
    return collapse_ws("".join(chars))


def _strip_example_ask(rest: str) -> str:
    remaining = rest
    changed = True
    while changed:
        changed = False
        for tail in _EXAMPLE_TAILS:
            if remaining.startswith(tail):
                remaining = remaining[len(tail) :].strip()
                changed = True
            elif remaining.endswith(tail):
                remaining = remaining[: -len(tail)].strip()
                changed = True
    return remaining


def _remainder_is_examples_or_filler(rest: str) -> bool:
    stripped = _strip_example_ask(_letters_and_spaces(rest))
    if not stripped:
        return True
    return all(token in _FILLER_WORDS for token in stripped.split())


def is_capabilities_question(text: str) -> bool:
    """True for 'what can you do' overviews, including the Home chip prompt."""
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned) > _MAX_CAPABILITIES_CHARS:
        return False
    if writing_request_kind(cleaned) is not None:
        return False
    folded = _fold_capabilities_text(cleaned)
    folded_exact = _letters_and_spaces(folded)
    for exact in _CAPABILITIES_EXACT:
        if folded_exact == _letters_and_spaces(exact):
            return True
    for stem in _CAPABILITIES_STEMS:
        index = folded.find(stem)
        if index < 0 or index > _STEM_MAX_START:
            continue
        rest = folded[index + len(stem) :]
        if _remainder_is_examples_or_filler(rest):
            return True
    return False
