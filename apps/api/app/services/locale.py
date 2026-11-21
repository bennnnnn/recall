"""User locale → human-readable language hints for LLM system prompts."""

from __future__ import annotations

from app.core.validation import LOCALE_NAMES as LOCALE_NAMES
from app.core.validation import normalize_locale_code as normalize_locale_code

# Languages a user may name, in English, whether or not the app offers them: "put that in
# German" asks for the reply in German though German is no app language (2026-11-20: once
# German left the app's languages, it read as a to-do list called "German"). The app's own
# languages are among them (``test_language_names_hold_the_apps``).
LANGUAGE_NAMES = frozenset(
    {
        "afrikaans", "albanian", "amharic", "arabic", "armenian", "azerbaijani", "basque",
        "belarusian", "bengali", "bosnian", "bulgarian", "burmese", "cantonese", "catalan",
        "chinese", "croatian", "czech", "danish", "dutch", "english", "estonian", "farsi",
        "filipino", "finnish", "french", "georgian", "german", "greek", "gujarati", "hausa",
        "hebrew", "hindi", "hungarian", "icelandic", "igbo", "indonesian", "irish", "italian",
        "japanese", "kannada", "kazakh", "khmer", "korean", "kurdish", "lao", "latin",
        "latvian", "lithuanian", "macedonian", "malay", "malayalam", "mandarin", "marathi",
        "mongolian", "nepali", "norwegian", "oromo", "pashto", "persian", "polish",
        "portuguese", "punjabi", "romanian", "russian", "serbian", "sinhala", "slovak",
        "slovenian", "somali", "spanish", "swahili", "swedish", "tagalog", "tamil", "telugu",
        "thai", "tigrinya", "turkish", "ukrainian", "urdu", "uzbek", "vietnamese", "welsh",
        "xhosa", "yiddish", "yoruba", "zulu",
    }
)  # fmt: skip


def locale_display_name(locale: str | None) -> str:
    code = normalize_locale_code(locale)
    return LOCALE_NAMES.get(code, locale or "English")


# An English app got no language line, so a saved "replies in Spanish" and then the Spanish
# reply above it decided: "Teach me how to improve recall" was answered in Spanish, and the
# English messages after it too (2026-10-24).
REPLY_LANGUAGE_ORDER = (
    "If their custom instructions name a reply language, use it. Otherwise write in the "
    "language of their latest message; a message with no language of its own (a number, "
    "'ok', code, a photo) keeps the language of their message before it. A saved memory, "
    "an earlier chat or an earlier reply in another language never sets it."
)


def locale_system_hint(locale: str | None) -> str:
    """The reply language: their instructions, then their message, then the app's."""
    code = normalize_locale_code(locale)
    name = locale_display_name(code)
    return (
        f"The user's app language is {name} (locale code: {code}): write replies in {name} "
        f"unless they write in another language or ask in this conversation for one. "
        f"When the user changes app language, follow it at once. " + REPLY_LANGUAGE_ORDER
    )
