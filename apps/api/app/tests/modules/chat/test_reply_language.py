"""A reply is written in the language of the user's message, whatever a memory says.

With "User prefers replies in Spanish" saved, an English app's "Teach me how to improve
recall" was answered in Spanish three times in three, though the language line ranked a
saved memory last (2026-10-24). The note beside the message names its language.
"""

from __future__ import annotations

import pytest

from app.modules.chat.reply_language import reply_language_hint


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Teach me how to improve recall", "English"),
        ("What?", "English"),
        ("What’s my name?", "English"),  # the iPhone's apostrophe
        ("El Niño is coming this year", "English"),
        ("¿Qué es la fotosíntesis?", "Spanish"),
        ("Erinnere mich morgen an das Meeting", "German"),
        ("Привет, как дела?", "Russian"),
        ("ሰላም እንዴት ነህ", "Amharic"),
    ],
)
def test_a_message_in_a_language_gets_its_reply_in_it(query: str, language: str) -> None:
    hint = reply_language_hint(query, [], None)
    assert hint is not None and hint.startswith(f"Write this reply in {language},")


@pytest.mark.parametrize("query", ["ok", "17:00", "x = 2y + 3", "👍", ""])
def test_a_message_with_no_language_keeps_the_chats(query: str) -> None:
    assert reply_language_hint(query, [], None) is None


def test_a_language_they_asked_for_in_this_chat_stays_theirs() -> None:
    prior = [("user", "reply in Spanish from now on"), ("assistant", "¡Claro!")]
    assert reply_language_hint("Teach me how to improve recall", prior, None) is None
    asked = [("user", "can you answer me in French please"), ("assistant", "Bien sûr.")]
    assert reply_language_hint("What is a verb?", asked, None) is None


@pytest.mark.parametrize("instructions", ["Always answer in Amharic.", "Use my language."])
def test_custom_instructions_naming_a_language_win(instructions: str) -> None:
    assert reply_language_hint("Teach me how to improve recall", [], instructions) is None


def test_other_custom_instructions_leave_the_note() -> None:
    assert reply_language_hint("Teach me how to improve recall", [], "Keep it upbeat.")
