# ruff: noqa: RUF002 - Turkish dotless i is part of the words tested
"""Everyday and teaching lines in other languages that use a picture verb, and draw nothing.

Each was drawn by the first version of the other-language reader (a review found them);
each English twin draws nothing ("illustrate with an example", "draw an example", "draw
caffeine" goes to chemistry, "draw it again" is the chat's).
"""

from __future__ import annotations

import pytest

from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.gen_intent import (
    extract_image_gen_prompt,
    picture_and_request,
    picture_language,
)
from app.modules.images.intent import image_gen_request

# Teaching asks: English "NON_IMAGE_WORDS" in each language.
TEACHING = [
    "Ilustra con un ejemplo",
    "Illustra con un esempio",
    "Illustre avec un exemple",
    "Ilustre com um exemplo",
    "Ilustra la solución",
    "Illustre la solution",
    "Illustra la soluzione",
    "Illustriere die Lösung",
    "Ilustra tu respuesta con un ejemplo",
    "Illustra la tua risposta con un esempio",
    "Dibuja un ejemplo",
    "Dessine un exemple",
    "Zeichne ein Beispiel",
    "Disegna un esempio",
    "Desenhe um exemplo",
    "Нарисуй пример",
    "Bir örnek çiz",
    "Ilustra el problema",
    "Illustra il problema",
    "Illustra un esercizio",
    "Dibuja mi tarea",
    "Dibuja el proyecto",
    "Disegna un progetto per la mia startup",
    "Illustre le résumé",
    "Dibuja una página web",
    "Zeichne meine Matheaufgabe",
    "Нарисуй мою домашку",
    "Ödevimi çiz",
    "Ilustra la diferencia entre ser y estar",
]

# Maths, physics and chemistry: English hands their twins to the subject.
STEM = [
    "Dibuja la cafeína",
    "Dibuja el benceno",
    "Dibuja etanol",
    "Dibuja la aspirina",
    "Dibuja el ácido acético",
    "Dessine la caféine",
    "Disegna la caffeina",
    "Desenhe a cafeína",
    "Zeichne Koffein",
    "Нарисуй кофеин",
    "Нарисуй этанол",
    "Kafein çiz",
    "Dibuja las fuerzas que actúan sobre un bloque en un plano inclinado",
    "Zeichne die Kräfte auf einen Block auf einer schiefen Ebene",
    "Нарисуй силы, действующие на брусок на наклонной плоскости",
    "Dibuja un circuito con dos resistencias en serie",
    "Zeichne einen Stromkreis mit zwei Widerständen in Reihe",
    "Dibuja el campo eléctrico de un dipolo",
    "Dibuja los rayos de una lente convexa",
    "Zeichne den Strahlengang einer Sammellinse",
    "Zeichne eine Sinuswelle",
    "Dessine une cellule végétale",
    "Disegna un atomo",
    "Desenhe a estrutura do DNA",
    "Bir hücre çiz",
    "Нарисуй параболу",
]

# "Pinta bien" says how something looks; "изобрази удивление" asks to act surprised.
LOOKS = [
    "Pinta bien",
    "¡Pinta bien!",
    "Pinta mal",
    "Pinta genial",
    "Pinta interesante",
    "Pinta fatal",
    "Pinta feo",
    "Pinta muy bien tu proyecto",
    "Pinta que va a llover",
    "Изобрази удивление",
]

# Pointing back, in any language ("Pinta isso" is Portuguese read with Spanish words).
POINTS_BACK = ["Pinta isso", "Ilustre isso", "Pinte isso de novo", "Pinte o fluxograma do processo"]

# German separable verbs: "ausmalen" imagines, "aufzeichnen" writes down.
SEPARABLE = ["Male mir aus, wie es wäre", "Zeichne mir auf, wie das geht"]


@pytest.mark.parametrize("text", TEACHING + STEM + LOOKS + POINTS_BACK + SEPARABLE)
def test_draws_nothing(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
    assert image_gen_request(text, []) is None
    assert not plan_turn(text).of_kind("image")


def test_a_look_is_not_a_picture_part() -> None:
    assert not plan_turn("Pinta bien, y dime qué más necesitas").of_kind("image")


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        # With an article the verb paints, in both languages.
        ("Pinta un gato", "gato"),
        ("Pinte um gato", "gato"),
        # What a picture is for is not its subject ("draw a cat for my project").
        ("Dibuja un gato para mi proyecto", "gato para mi proyecto"),
        ("Изобрази мне кошку", "кошку"),
    ],
)
def test_still_drawn(text: str, subject: str) -> None:
    assert extract_image_gen_prompt(text) == subject


@pytest.mark.parametrize(
    ("prefer", "lang"), [("pt", "pt"), ("es", "es"), (None, "es"), ("de", "es")]
)
def test_a_shared_verb_takes_the_apps_language(prefer: str | None, lang: str) -> None:
    assert picture_language("Pinte um gato", prefer) == lang


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        # Details of the picture after "and" or a full stop, not a second request:
        # "ne" is French, "come" is "like", "écris" / "gib" / "zeig" add to the picture.
        ("Dessine un chat et ne mets pas de chapeau", "chat et ne mets pas de chapeau"),
        ("Disegna un gatto. Come un leone, però.", "gatto. Come un leone, però"),
        ("Dibuja un gato y escribe su nombre debajo", "gato y escribe su nombre debajo"),
        ("Zeichne eine Katze und gib ihr einen Hut", "Katze und gib ihr einen Hut"),
        ("Нарисуй кошку и как она спит", "кошку и как она спит"),
    ],
)
def test_a_detail_after_and_stays_in_the_picture(text: str, subject: str) -> None:
    assert picture_and_request(text) is None
    assert extract_image_gen_prompt(text) == subject


def test_turkish_summer_stays_in_the_picture() -> None:
    """ "yaz" is "write" and "summer": "…, yaz mevsiminde" after the verb still describes
    the picture; a Turkish ask after the comma ("…, kara deliği açıkla") is cut off."""
    assert picture_and_request("Bir kedi çiz, yaz mevsiminde") is None
    assert extract_image_gen_prompt("Bir kedi çiz, yaz mevsiminde") == "kedi, yaz mevsiminde"
    parts = picture_and_request("Bir kedi çiz, kara deliği açıkla")
    assert parts is not None
    assert [(part.text, part.picture) for part in parts] == [
        ("Bir kedi çiz", True),
        ("kara deliği açıkla", False),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Explica cómo se dibuja un gato",
        "Erkläre mir, wie man eine Katze zeichnet",
        "Explica qué es un agujero negro y dibuja la gráfica",
    ],
)
def test_no_picture_part_after_a_question_about_drawing(text: str) -> None:
    assert picture_and_request(text) is None


def test_english_draw_me_with_a_second_request_draws_only_the_picture_part() -> None:
    """The whole line drew "cat and also explain black holes" and lost the question."""
    text = "draw me a cat and also explain black holes"
    assert extract_image_gen_prompt(text) is None
    assert [(part.kind, part.text) for part in plan_turn(text).parts] == [
        ("image", "draw me a cat"),
        ("ask", "explain black holes"),
    ]
