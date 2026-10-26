"""A picture and a second request in one message, in each of the app's languages.

"Draw a cat wearing a hat and also explain what a black hole is" draws the cat above the
answer. Asked in German, Spanish or Russian, the plan was one part and nothing was
drawn: the picture and the cut were read only in English.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat.turn_intercepts import reply_picture_prompt, start_reply_picture
from app.modules.chat.turn_prep.intents import plan_turn
from app.tests.modules.images.test_gen_intent_languages import DRAW

# The picture, then "… and also explain what a black hole is" in the same language.
NATIVE = [
    ("en", "Draw a cat with a hat and also explain what a black hole is", "cat with a hat"),
    (
        "es",
        "Dibuja un gato con sombrero y también explica qué es un agujero negro",
        "gato con sombrero",
    ),
    (
        "fr",
        "Dessine un chat avec un chapeau et explique aussi ce qu'est un trou noir",
        "chat avec un chapeau",
    ),
    (
        "de",
        "Zeichne eine Katze mit Hut und erkläre auch, was ein schwarzes Loch ist",
        "Katze mit Hut",
    ),
    (
        "it",
        "Disegna un gatto con il cappello e spiega anche cos'è un buco nero",
        "gatto con il cappello",
    ),
    (
        "pt",
        "Desenhe um gato com chapéu e também explique o que é um buraco negro",
        "gato com chapéu",
    ),
    (
        "tr",
        "Şapkalı bir kedi çiz ve ayrıca kara deliğin ne olduğunu açıkla",
        "Şapkalı bir kedi",
    ),
    (
        "ru",
        "Нарисуй кошку в шляпе, а также объясни, что такое чёрная дыра",
        "кошку в шляпе",
    ),
    ("am", "ድመት ሳልልኝ እንዲሁም ጥቁር ቀዳዳ ምን እንደሆነ አስረዳኝ", "ድመት"),
]


@pytest.mark.parametrize(("lang", "text", "subject"), NATIVE)
def test_a_picture_and_a_question_plan_as_two_parts(lang: str, text: str, subject: str) -> None:
    plan = plan_turn(text)
    assert [part.kind for part in plan.parts] == ["image", "ask"], lang
    assert reply_picture_prompt(text, Settings()) == subject


@pytest.mark.parametrize(("lang", "text", "subject"), DRAW)
def test_the_picture_part_reads_before_an_english_question(
    lang: str, text: str, subject: str
) -> None:
    """The owner's measurement: "<X> and also explain what a black hole is"."""
    message = f"{text} and also explain what a black hole is"
    assert reply_picture_prompt(message, Settings()) == subject, lang


@pytest.mark.parametrize(
    "text",
    [
        # One picture of two things, a table, a graph: one request, nothing drawn beside it.
        "Dibuja un gato y un perro",
        "Zeichne mir eine Tabelle der Ergebnisse und erkläre sie",
        "Нарисуй график функции и объясни его",
        "grafik çiz ve açıkla",
    ],
)
def test_no_picture_part_for_a_table_a_graph_or_one_picture(text: str) -> None:
    assert not plan_turn(text).of_kind("image")
    assert reply_picture_prompt(text, Settings()) is None


# How the not-drawn line under the answer starts, in each language.
LINE_START = {
    "en": "I couldn't draw the picture (",
    "es": "Esta vez no pude dibujar la imagen (",
    "fr": "Je n'ai pas pu dessiner l'image (",
    "de": "Das Bild (",
    "it": "Questa volta non sono riuscito a disegnare l'immagine (",
    "pt": "Desta vez não consegui desenhar a imagem (",
    "tr": "Bu sefer resmi (",
    "ru": "В этот раз не удалось нарисовать картинку (",
    "am": "ምስሉን (",
}

# Asked second ("explain …, and draw a cat"), as English "… and also draw a cat" is.
PICTURE_SECOND = [
    ("es", "Explica qué es un agujero negro y dibuja un gato", "gato"),
    ("es", "¿Qué es un agujero negro? Dibuja un gato", "gato"),
    ("fr", "Explique ce qu'est un trou noir et dessine un chat", "chat"),
    ("de", "Erkläre, was ein schwarzes Loch ist, und zeichne auch eine Katze", "Katze"),
    ("it", "Spiegami cos'è un buco nero e disegna un gatto", "gatto"),
    ("pt", "Explique o que é um buraco negro e desenhe um gato", "gato"),
    ("tr", "Kara deliğin ne olduğunu açıkla ve bir kedi çiz", "kedi"),
    ("ru", "Объясни, что такое чёрная дыра, и нарисуй кошку", "кошку"),
    ("am", "ጥቁር ቀዳዳ ምን እንደሆነ አስረዳኝ እንዲሁም ድመት ሳልልኝ", "ድመት"),
]


def _not_drawn_line(text: str, locale: str) -> tuple[str, str]:
    class _Plan:
        @staticmethod
        def can_use(*_args: object) -> bool:
            return True

    class _Deps:
        plan = _Plan()

    picture = start_reply_picture(
        _Deps(),  # type: ignore[arg-type]
        Settings(image_generation_enabled=False),
        user=User(id=uuid4(), plan="pro", locale=locale),
        chat_id=uuid4(),
        content=text,
    )
    assert picture is not None
    text_with_line, ids = asyncio.run(picture.attach("…"))
    assert ids == []
    return picture.subject, text_with_line.removeprefix("…").strip()


@pytest.mark.parametrize(("lang", "text", "subject"), NATIVE[1:] + PICTURE_SECOND)
def test_the_picture_starts_beside_the_answer_with_its_line_in_the_message_language(
    lang: str, text: str, subject: str
) -> None:
    """An English app: the line is the message's language's, named exactly."""
    drawn, line = _not_drawn_line(text, "en")
    assert drawn == subject
    assert line.startswith(LINE_START[lang]), line


@pytest.mark.parametrize(("lang", "text", "subject"), PICTURE_SECOND)
def test_a_picture_asked_second_plans_after_the_answer(lang: str, text: str, subject: str) -> None:
    plan = plan_turn(text)
    assert [part.kind for part in plan.parts] == ["ask", "image"], lang
    assert reply_picture_prompt(text, Settings()) == subject


@pytest.mark.parametrize(("locale", "lang"), [("pt-BR", "pt"), ("es", "es"), ("en", "es")])
def test_a_verb_spanish_and_portuguese_share_takes_the_apps_language(
    locale: str, lang: str
) -> None:
    """ "Pinte um gato e explique …" reads the same in both; the app's language decides,
    and an English app keeps the first reading."""
    _drawn, line = _not_drawn_line("Pinte um gato e explique o que é um buraco negro", locale)
    assert line.startswith(LINE_START[lang]), line
