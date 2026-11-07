# ruff: noqa: RUF001
"""The words the server writes into a lesson, in each of the app's languages.

The language is the one a server line takes (``reply_language.line_language``): the
message's own when it is plainly one of the app's languages, else the app's. Each word for
"Lesson" is one ``turn_reading.lesson_flow`` reads back as a lesson title.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.chat.reply_language import line_language


@dataclass(frozen=True)
class LessonCopy:
    lesson: str  # "Lesson", as in "### Lesson 1: Recursion"
    your_turn: str  # the practice section's heading
    exercise: str  # the practice card's label


_COPY: dict[str, LessonCopy] = {
    "en": LessonCopy(
        "Lesson",
        "Your turn",
        "Exercise 1",
    ),
    "es": LessonCopy(
        "Lección",
        "Tu turno",
        "Ejercicio 1",
    ),
    "fr": LessonCopy(
        "Leçon",
        "À toi",
        "Exercice 1",
    ),
    "de": LessonCopy(
        "Lektion",
        "Du bist dran",
        "Übung 1",
    ),
    "it": LessonCopy(
        "Lezione",
        "Tocca a te",
        "Esercizio 1",
    ),
    "pt": LessonCopy(
        "Lição",
        "Sua vez",
        "Exercício 1",
    ),
    "ru": LessonCopy(
        "Урок",
        "Твоя очередь",
        "Упражнение 1",
    ),
    "tr": LessonCopy(
        "Ders",
        "Sıra sende",
        "Alıştırma 1",
    ),
    "am": LessonCopy(
        "ትምህርት",
        "የእርስዎ ተራ",
        "መልመጃ 1",
    ),
}


def lesson_copy(message: str, locale: Any) -> LessonCopy:
    """The server's lesson words in the language of the reply to ``message``."""
    return _COPY.get(line_language(message, locale), _COPY["en"])
