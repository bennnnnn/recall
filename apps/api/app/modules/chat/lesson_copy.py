# ruff: noqa: RUF001
"""The words the server writes into a lesson or an outline, in each of the app's languages.

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
    where_to_start: str  # an outline's closing question


_COPY: dict[str, LessonCopy] = {
    "en": LessonCopy(
        "Lesson",
        "Your turn",
        "Exercise 1",
        "Where would you like to start? Pick a number, or tell me what you already know.",
    ),
    "es": LessonCopy(
        "Lección",
        "Tu turno",
        "Ejercicio 1",
        "¿Por dónde quieres empezar? Elige un número o cuéntame qué sabes ya.",
    ),
    "fr": LessonCopy(
        "Leçon",
        "À toi",
        "Exercice 1",
        "Par où veux-tu commencer ? Choisis un numéro ou dis-moi ce que tu sais déjà.",
    ),
    "de": LessonCopy(
        "Lektion",
        "Du bist dran",
        "Übung 1",
        "Wo möchtest du anfangen? Wähle eine Nummer oder sag mir, was du schon weißt.",
    ),
    "it": LessonCopy(
        "Lezione",
        "Tocca a te",
        "Esercizio 1",
        "Da dove vuoi iniziare? Scegli un numero o dimmi cosa sai già.",
    ),
    "pt": LessonCopy(
        "Lição",
        "Sua vez",
        "Exercício 1",
        "Por onde você quer começar? Escolha um número ou me diga o que já sabe.",
    ),
    "ru": LessonCopy(
        "Урок",
        "Твоя очередь",
        "Упражнение 1",
        "С чего хочешь начать? Выбери номер или расскажи, что уже знаешь.",
    ),
    "tr": LessonCopy(
        "Ders",
        "Sıra sende",
        "Alıştırma 1",
        "Nereden başlamak istersin? Bir numara seç ya da bildiklerini söyle.",
    ),
    "am": LessonCopy(
        "ትምህርት",
        "የእርስዎ ተራ",
        "መልመጃ 1",
        "ከየት መጀመር ይፈልጋሉ? ቁጥር ይምረጡ ወይም አስቀድመው የሚያውቁትን ይንገሩኝ።",
    ),
}


def lesson_copy(message: str, locale: Any) -> LessonCopy:
    """The server's lesson words in the language of the reply to ``message``."""
    return _COPY.get(line_language(message, locale), _COPY["en"])
