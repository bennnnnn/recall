"""Which language a chat message is in, and the To-do line in each app language."""

from __future__ import annotations

import pytest

from app.modules.todos.chat_language import (
    answer_language,
    message_language,
    todo_screen_line,
)


@pytest.mark.parametrize(
    "text",
    [
        "recuérdame mañana a las 9 llamar a mamá",
        "¿qué tengo hoy?",
        "rappelle-moi demain d'appeler ma mère",
        "lembra-me amanhã de ligar para a minha mãe",
        "напомни завтра позвонить маме",
        "yarın annemi aramayı hatırlat",
        "ነገ እናቴን እንድደውል አስታውሰኝ",
        "कल मुझे माँ को फ़ोन करने की याद दिलाना",
        "आज मेरे पास क्या है?",
        "ዛሬ ምን አለኝ?",
    ],
)
def test_a_to_do_message_in_any_app_language_loads_the_list(text: str) -> None:
    """The list reaches the prompt, so a question is answered from it and an ask to add
    one gets the To-do button instead of a guess."""
    from app.modules.todos import query_implies_todos

    assert query_implies_todos(text) is True


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("recuérdame mañana a las 9 llamar a mamá", "es"),
        ("rappelle-moi demain d'appeler ma mère", "fr"),
        # German and Italian are no app language, but are still read as not English.
        ("erinnere mich morgen um 9 Uhr an den Zahnarzt", "de"),
        ("ricordami domani alle 9 di chiamare la mamma", "it"),
        ("lembra-me amanhã às 9 de ligar para a minha mãe", "pt"),
        ("yarın saat 9'da annemi aramayı hatırlat", "tr"),
        ("напомни завтра в 9 позвонить маме", "ru"),
        ("ነገ 9 ሰዓት እናቴን እንድደውል አስታውሰኝ", "am"),
        ("कल सुबह 9 बजे माँ को फ़ोन करने की याद दिलाना", "hi"),
        # Another script the app has no language for, and plain English.
        ("ذكرني غدا بالاتصال بأمي", None),
        ("remind me to call mom", None),
        ("", None),
        (None, None),
    ],
)
def test_message_language_names_the_app_language_a_message_is_in(
    text: str | None, language: str | None
) -> None:
    assert message_language(text) == language


@pytest.mark.parametrize("language", ["es", "fr", "pt", "tr", "ru", "am", "hi"])
def test_every_app_language_has_its_own_to_do_line(language: str) -> None:
    line = todo_screen_line(language)
    assert line != todo_screen_line("en")
    # It names the screen and never claims the change was made.
    assert line.count("**") == 2


def test_an_unknown_language_gets_the_english_line() -> None:
    assert (
        todo_screen_line(None) == todo_screen_line("xx") == "You can add or change it in **To-do**."
    )


@pytest.mark.parametrize(
    ("text", "prior_user", "locale", "language"),
    [
        ("remind me to call mom", None, "es", "en"),
        # English grammar around the request keeps it English, whatever script its object is in.
        ("remind me to buy молоко хлеб сыр", None, "ru", "en"),
        ("напомни завтра позвонить маме", None, "en", "ru"),
        ("कल सुबह 9 बजे remind करना", None, "en", "hi"),
        # A message with no language of its own follows the chat, then the app language.
        ("a las 5", "recuérdame llamar a mamá", "en", "es"),
        ("17:00", None, "tr", "tr"),
    ],
)
def test_the_to_do_line_answers_in_the_messages_language(
    text: str, prior_user: str | None, locale: str, language: str
) -> None:
    assert answer_language(text, prior_user=prior_user, locale=locale) == language
