import pytest

from app.services.locale import locale_display_name, locale_system_hint, normalize_locale_code


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


def test_locale_system_hint_english_none():
    assert locale_system_hint("en") is None
    assert locale_system_hint(None) is None


def test_locale_system_hint_amharic():
    hint = locale_system_hint("am")
    assert hint is not None
    assert "Amharic" in hint
    assert "am" in hint
    assert "switch languages" in hint.lower() or "switch language" in hint.lower()
