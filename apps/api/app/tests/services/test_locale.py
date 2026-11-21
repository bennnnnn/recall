import pytest

from app.core.validation import LOCALE_NAMES
from app.services.locale import REPLY_LANGUAGE_ORDER, locale_display_name, locale_system_hint


@pytest.mark.parametrize(
    "locale, expected",
    [
        ("am", "Amharic"),
        ("es", "Spanish"),
        ("en-US", "English"),
        (None, "English"),
    ],
)
def test_locale_display_name(locale, expected):
    assert locale_display_name(locale) == expected


def test_an_english_app_names_its_reply_language_and_what_outranks_it():
    """An English app had no language line; a saved "replies in Spanish" decided instead."""
    for locale in ("en", None, "en-US"):
        hint = locale_system_hint(locale)
        assert hint.startswith("The user's app language is English (locale code: en)")
        assert hint.endswith(REPLY_LANGUAGE_ORDER)


def test_locale_system_hint_amharic():
    hint = locale_system_hint("am")
    assert hint is not None
    assert "Amharic" in hint
    assert "am" in hint
    assert hint.endswith(REPLY_LANGUAGE_ORDER)


def test_language_names_hold_the_apps():
    """Every app language is a language a user may name, and so are languages the app
    does not offer: the names never follow the language menu."""
    from app.services.locale import LANGUAGE_NAMES

    assert {name.lower() for name in LOCALE_NAMES.values()} <= LANGUAGE_NAMES
    assert {"german", "italian", "japanese"} <= LANGUAGE_NAMES


@pytest.mark.parametrize(
    ("typed", "unified"),
    [
        ("अंग्रेज़ी", "अंग्रेज़ी"),  # ज़ as one sign
        ("अंग्रेज़ी", "अंग्रेज़ी"),  # already its letter and dot
        ("ऩ", "ऩ"),
        ("plain text", "plain text"),
        ("résumé", "résumé"),  # other scripts' accents are left alone
    ],
)
def test_unify_devanagari(typed: str, unified: str) -> None:
    from app.core.validation import unify_devanagari

    assert unify_devanagari(typed) == unified
