"""User locale → human-readable language hints for LLM system prompts."""

from __future__ import annotations

from app.core.validation import LOCALE_NAMES as LOCALE_NAMES
from app.core.validation import normalize_locale_code as normalize_locale_code


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
