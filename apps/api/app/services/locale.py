"""User locale → human-readable language hints for LLM system prompts."""

from __future__ import annotations

# ISO 639-1 codes supported by the mobile app (see apps/mobile/lib/i18n/languages.ts).
LOCALE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "tr": "Turkish",
    "am": "Amharic",
}


def normalize_locale_code(locale: str | None) -> str:
    if not locale:
        return "en"
    return locale.split("-")[0].lower()


def locale_display_name(locale: str | None) -> str:
    code = normalize_locale_code(locale)
    return LOCALE_NAMES.get(code, locale or "English")


def locale_system_hint(locale: str | None) -> str | None:
    """Strong instruction for the model when UI language is not English."""
    code = normalize_locale_code(locale)
    if code == "en":
        return None
    name = locale_display_name(code)
    return (
        f"The user's app language is {name} (locale code: {code}). "
        f"Always write replies in {name} unless the user writes in another language "
        f"or explicitly asks you to switch languages. "
        f"When the user changes app language, follow the latest preference immediately — "
        f"do not keep replying in a previous language."
    )
