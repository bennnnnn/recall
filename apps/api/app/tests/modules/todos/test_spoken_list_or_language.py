"""A move's target is a list unless it names a language: "put that in German" asks for the
reply in German, whether or not German is one of the app's languages (2026-11-20)."""

from __future__ import annotations

import pytest

from app.modules.todos.spoken_apply import _a_list
from app.modules.todos.spoken_change import parse_spoken_reminder_change


@pytest.mark.parametrize("language", ["German", "Italian", "Hindi", "Spanish", "Japanese"])
def test_a_language_is_no_list(language: str) -> None:
    spoken = parse_spoken_reminder_change(f"put that in {language}")
    assert spoken is not None and spoken.topic == language
    assert not _a_list(spoken, None, False)


def test_a_list_name_is_still_a_list() -> None:
    spoken = parse_spoken_reminder_change("put that in Groceries")
    assert spoken is not None
    assert _a_list(spoken, None, False)
