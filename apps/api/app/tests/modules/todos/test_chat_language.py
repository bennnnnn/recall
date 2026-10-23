"""Chat adds and changes to-dos only from English messages; others use To-do."""

from __future__ import annotations

import pytest

from app.modules.todos.chat_language import writes_todos_in_todo_screen


@pytest.mark.parametrize(
    "text",
    [
        "recuérdame mañana a las 9 llamar a mamá",
        "agrega pan a mi lista",
        "¿qué tengo hoy?",
        "rappelle-moi demain d'appeler ma mère",
        "ajoute du lait à ma liste",
        "erinnere mich morgen um 9 Uhr an den Zahnarzt",
        "ricordami domani alle 9 di chiamare la mamma",
        "lembra-me amanhã às 9 de ligar para a minha mãe",
        "yarın saat 9'da annemi aramayı hatırlat",
        "напомни завтра в 9 позвонить маме",
        "ነገ 9 ሰዓት እናቴን እንድደውል አስታውሰኝ",
    ],
)
def test_a_message_in_another_language_changes_to_dos_in_the_todo_screen(text: str) -> None:
    assert writes_todos_in_todo_screen(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "remind me to call mom tomorrow at 9",
        "add milk to my list",
        "mark the dentist done",
        # An English to-do word keeps a mixed message English.
        "remind me to call Getachew ነገ at 10am",
        "remind me to fly to Los Angeles on Friday",
        "remind me tonight at 9 to text selam happy birthday 🎂",
        "done ✅ just talked to her",
        # One word of another language is not enough to tell.
        "call mom mañana",
        "",
        "   ",
        None,
    ],
)
def test_an_english_message_still_changes_to_dos_in_chat(text: str | None) -> None:
    assert writes_todos_in_todo_screen(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "recuérdame mañana a las 9 llamar a mamá",
        "¿qué tengo hoy?",
        "rappelle-moi demain d'appeler ma mère",
        "erinnere mich morgen an den Zahnarzt",
        "ricordami domani di chiamare la mamma",
        "lembra-me amanhã de ligar para a minha mãe",
        "напомни завтра позвонить маме",
        "yarın annemi aramayı hatırlat",
        "ነገ እናቴን እንድደውል አስታውሰኝ",
    ],
)
def test_a_to_do_message_in_any_app_language_loads_the_list(text: str) -> None:
    """The list reaches the prompt, so a question is answered from it and an ask to add
    one gets the To-do button instead of a guess."""
    from app.modules.todos import query_implies_todos

    assert query_implies_todos(text) is True
