"""A picture and a second request in one message, in each of the app's languages.

"Draw a cat wearing a hat and also explain what a black hole is" draws the cat above the
answer. Asked in German, Spanish or Russian, the plan was one part and nothing was
drawn: the picture and the cut were read only in English. Now a draw-me picture
("Zeichne mir eine Katze …", "Dibújame un gato …") is cut off and drawn there too.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat.turn_intercepts import reply_picture_part, start_reply_picture
from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.gen_intent import extract_image_gen_prompt
from app.tests.modules.images.test_gen_intent_languages import DRAWN

# The picture, then "… and also explain what a black hole is" in the same language.
NATIVE = [
    ("en", "Draw a cat with a hat and also explain what a black hole is", "cat with a hat"),
    (
        "es",
        "Dibújame un gato con sombrero y también explica qué es un agujero negro",
        "gato con sombrero",
    ),
    (
        "fr",
        "Dessine-moi un chat avec un chapeau et explique aussi ce qu'est un trou noir",
        "chat avec un chapeau",
    ),
    (
        "de",
        "Zeichne mir eine Katze mit Hut und erkläre auch, was ein schwarzes Loch ist",
        "Katze mit Hut",
    ),
    (
        "it",
        "Disegnami un gatto con il cappello e spiega anche cos'è un buco nero",
        "gatto con il cappello",
    ),
    (
        "pt",
        "Me desenhe um gato com chapéu e também explique o que é um buraco negro",
        "gato com chapéu",
    ),
    (
        "tr",
        "Bana şapkalı bir kedi çiz ve ayrıca kara deliğin ne olduğunu açıkla",
        "şapkalı bir kedi",
    ),
    (
        "ru",
        "Нарисуй мне кошку в шляпе, а также объясни, что такое чёрная дыра",
        "кошку в шляпе",
    ),
    ("am", "ድመት ሳልልኝ እንዲሁም ጥቁር ቀዳዳ ምን እንደሆነ አስረዳኝ", "ድመት"),
]


def _drawn_part(text: str) -> str | None:
    """What the picture part of ``text`` draws, as ``start_reply_picture`` reads it."""
    part = reply_picture_part(text, Settings())
    return extract_image_gen_prompt(part) if part else None


# One drawn request per language, for the English question after it.
FIRST_DRAWN = [(lang, *cases[0]) for lang, cases in DRAWN.items()]


@pytest.mark.parametrize(("lang", "text", "subject"), NATIVE)
def test_a_picture_and_a_question_plan_as_two_parts(lang: str, text: str, subject: str) -> None:
    plan = plan_turn(text)
    assert [part.kind for part in plan.parts] == ["image", "ask"], lang
    assert _drawn_part(text) == subject


@pytest.mark.parametrize(("lang", "text", "subject"), FIRST_DRAWN)
def test_the_picture_part_reads_before_an_english_question(
    lang: str, text: str, subject: str
) -> None:
    """The owner's measurement: "<X> and also explain what a black hole is"."""
    message = f"{text} and also explain what a black hole is"
    assert _drawn_part(message) == subject, lang


@pytest.mark.parametrize(
    "text",
    [
        # One picture of two things, a table, a graph, a bare "draw": no picture part.
        "Dibújame un gato y un perro",
        "Zeichne mir eine Tabelle der Ergebnisse und erkläre sie",
        "Нарисуй мне график функции и объясни его",
        "Bana grafik çiz ve açıkla",
        "Dibuja un gato y explica qué es un agujero negro",
    ],
)
def test_no_picture_part_for_a_table_a_graph_or_a_bare_draw(text: str) -> None:
    assert not plan_turn(text).of_kind("image")
    assert _drawn_part(text) is None


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

# Asked second ("explain …, and draw me a cat"), as English "… and also draw a cat" is.
PICTURE_SECOND = [
    ("es", "Explica qué es un agujero negro y dibújame un gato", "gato"),
    ("es", "¿Qué es un agujero negro? ¿Me dibujas un gato?", "gato"),
    ("es", "Explica la fotosíntesis y después dibújame un girasol", "girasol"),
    ("fr", "Explique ce qu'est un trou noir et dessine-moi un chat", "chat"),
    ("de", "Erkläre, was ein schwarzes Loch ist, und zeichne mir auch eine Katze", "Katze"),
    ("de", "Erkläre, was ein schwarzes Loch ist, und kannst du mir eine Katze malen?", "Katze"),
    ("it", "Spiegami cos'è un buco nero e disegnami un gatto", "gatto"),
    ("pt", "Explique o que é um buraco negro e me desenhe um gato", "gato"),
    ("pt", "Explique a fotossíntese e depois me desenhe um girassol", "girassol"),
    ("tr", "Kara deliğin ne olduğunu açıkla ve bana bir kedi çiz", "kedi"),
    ("tr", "Fotosentezi açıkla, sonra bana bir ayçiçeği çiz", "ayçiçeği"),
    ("ru", "Объясни, что такое чёрная дыра, и нарисуй мне кошку", "кошку"),
    ("ru", "Объясни фотосинтез, а потом нарисуй мне подсолнух", "подсолнух"),
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
@pytest.mark.parametrize("locale", ["en", "de"])
def test_the_picture_starts_beside_the_answer_with_its_line_in_the_message_language(
    lang: str, text: str, subject: str, locale: str
) -> None:
    """Whatever the app's language, the line is the message's language's, named exactly."""
    drawn, line = _not_drawn_line(text, locale)
    assert drawn == subject
    assert line.startswith(LINE_START[lang]), line


@pytest.mark.parametrize(("lang", "text", "subject"), PICTURE_SECOND)
def test_a_picture_asked_second_plans_after_the_answer(lang: str, text: str, subject: str) -> None:
    plan = plan_turn(text)
    assert [part.kind for part in plan.parts] == ["ask", "image"], lang
    assert _drawn_part(text) == subject
