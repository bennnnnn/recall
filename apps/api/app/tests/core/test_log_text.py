"""``log_safe``: a value from outside stays on its own log line, and ordinary text is untouched."""

from __future__ import annotations

import logging
import sys
from uuid import UUID

import pytest

from app.core.log_text import log_safe

_ID = UUID("3f2b8c1e-9a4d-4e6f-8b7a-1c2d3e4f5a6b")


@pytest.mark.parametrize(
    "value, shown",
    [
        ("chat-1\nERROR forged line", "chat-1\\nERROR forged line"),
        ("a\r\nb", "a\\r\\nb"),
        ("carriage\roverwrite", "carriage\\roverwrite"),
        ("tab\there", "tab\\there"),
        ("bell\x07 escape\x1b[31m null\x00", "bell\\x07 escape\\x1b[31m null\\x00"),
        ("vertical\x0bform\x0cfeed", "vertical\\x0bform\\x0cfeed"),
        ("delete\x7f next\x85line", "delete\\x7f next\\x85line"),
        ("line\u2028para\u2029end", "line\\u2028para\\u2029end"),
    ],
)
def test_log_safe_escapes_line_breaks_and_control_characters(value: str, shown: str) -> None:
    assert log_safe(value) == shown


@pytest.mark.parametrize(
    "value",
    [
        "openai/gpt-image-1",
        "$RCAnonymousID:8b6fe9f9d5ad4b8f9b5fa4a8b8c7e6e5",
        "rcwebhook:user:3f2b8c1e-9a4d-4e6f-8b7a-1c2d3e4f5a6b",
        "https://example.com/a?b=c&d=e#f",
        "héllo wörld, 日本語, emoji 🙂",
        "C:\\path\\with\\backslashes",
        "quotes ' and \" stay",
        _ID,
        12.5,
        8,
        None,
    ],
)
def test_log_safe_leaves_ordinary_values_as_logging_prints_them(value: object) -> None:
    """``%s`` in a log call prints ``str(value)``: an id, a slug, a URL or a number reads the same."""
    assert log_safe(value) == str(value)


def test_no_character_starts_a_new_line() -> None:
    """Every character Python reads as a line break comes out escaped, whatever it is."""
    breaks = [
        chr(code)
        for code in range(sys.maxunicode + 1)
        if not 0xD800 <= code <= 0xDFFF and len(f"a{chr(code)}b".splitlines()) > 1
    ]
    assert "\n" in breaks and "\u2028" in breaks
    shown = log_safe("".join(breaks))
    assert shown.splitlines() == [shown]
    assert shown.isprintable()


def test_a_logged_value_is_one_line(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        logging.getLogger("app.test").warning("chat_id=%s", log_safe("x\nERROR forged"))
    assert caplog.messages == ["chat_id=x\\nERROR forged"]
