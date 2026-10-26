# ruff: noqa: RUF002 - Turkish dotless i and Cyrillic are part of the words tested
"""Other-language lines with a picture verb route as their English translation does on main.

Where English draws ("draw a squirrel", "draw an atom", "draw a sine wave", "draw a
circuit with two resistors"), the other language draws. Where English draws nothing
("draw an example", "draw a table", "draw a triangle") or hands the line to a subject
("draw caffeine" is chemistry, "the forces on a block on an incline" physics), so does
the other language. Each English twin was checked on main.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.gen_intent import extract_image_gen_prompt
from app.modules.images.gen_intent_parts import picture_and_request, picture_language
from app.modules.images.intent import composer_image_intent, image_gen_request

# English draws nothing: NON_IMAGE_WORDS ("draw an example", "draw my homework").
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
]

# English hands these to a subject: compounds by name, forces on a body on a slope, maths.
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
    "Desenhe a estrutura do DNA",
    "Dibuja un triángulo",
    "Dessine une droite",
    "Zeichne eine Gerade",
]

# "Pinta bien" says how something looks ("looks good"); "изобрази удивление" is "act
# surprised" ("depict" is no English picture verb either).
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

# Pointing back, in any language, as English "draw it again" ("Pinta isso" is Portuguese
# read with Spanish words); and "the flowchart" as English "draw the flowchart".
POINTS_BACK = ["Pinta isso", "Ilustre isso", "Pinte isso de novo", "Pinte o fluxograma do processo"]

# German separable verbs: "ausmalen" imagines, "aufzeichnen" writes down.
SEPARABLE = ["Male mir aus, wie es wäre", "Zeichne mir auf, wie das geht"]

# English draws every twin of these on main ("draw a squirrel with a nut", "draw a parrot
# in a cage", "draw a cell", "draw an atom", "draw a parabola", "draw a circuit with two
# resistors in series", "draw the electric field of a dipole", "draw the limit"…). A
# word that is also a STEM or task word in some sense does not stop them.
DRAWN = [
    "Нарисуй белку с орехом",
    "Нарисуй попугая в клетке",
    "Нарисуй кота на письменном столе",
    "Нарисуй круглый торт со свечами",
    "Нарисуй волну",
    "Нарисуй музыканта с гитарой",
    "Нарисуй рыцаря, полного силы",
    "Нарисуй девочку, читающую книгу по истории",
    "Нарисуй клетку",
    "Нарисуй параболу",
    "Çizgi film tarzında bir köpek çiz",
    "Çizgi film karakteri gibi bir kedi çiz",
    "Kareli gömlekli bir adam çiz",
    "Van Gogh tablosu gibi bir manzara çiz",
    "Duvarda grafiti yapan bir çocuk çiz",
    "Bir planör çiz",
    "Bir hesap makinesi çiz",
    "Bir hücre çiz",
    "Zeichne eine Katze, die gerade schläft",
    "Zeichne einen Musiker mit Gitarre",
    "Zeichne das Meer mit großen Wellen",
    "Zeichne einen Surfer auf einer Riesenwelle",
    "Zeichne einen Ritter voller Kraft",
    "Zeichne eine Zelle",
    "Zeichne eine Sinuswelle",
    "Zeichne einen Stromkreis mit zwei Widerständen in Reihe",
    "Zeichne den Strahlengang einer Sammellinse",
    "Male eine Katze",
    "Dessine une voiture à grande vitesse",
    "Dessine un chat sous les rayons du soleil",
    "Dessine un bouton de rose",
    "Dessine un chevalier plein de force",
    "Dessine un chat à droite",
    "Dessine une cellule végétale",
    "Disegna un gatto a tema natalizio",
    "Disegna le onde del mare",
    "Disegna un gatto sotto i raggi del sole",
    "Disegna un gatto nell'angolo della stanza",
    "Disegna un cavaliere pieno di forza",
    "Disegna una cellula",
    "Disegna un atomo",
    "Desenhe uma onda gigante com um surfista",
    "Desenhe uma tempestade com raios",
    "Desenhe um gato sob os raios de sol",
    "Desenhe um cavaleiro cheio de força",
    "Desenhe uma célula",
    "Dibuja un gato con energía",
    "Dibuja una niña leyendo un libro de historia",
    "Dibuja una célula",
    "Dibuja un átomo",
    "Dibuja una onda sinusoidal",
    "Dibuja una parábola",
    "Dibuja los rayos de una lente convexa",
    "Dibuja un circuito con dos resistencias en serie",
    "Dibuja el campo eléctrico de un dipolo",
    "Dibuja el límite",
    "Pinta un gato",
    "Pinte um gato",
]


@pytest.mark.parametrize("text", TEACHING + STEM + LOOKS + POINTS_BACK + SEPARABLE)
def test_draws_nothing(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
    assert image_gen_request(text, []) is None
    assert not plan_turn(text).of_kind("image")


@pytest.mark.parametrize("text", DRAWN)
def test_draws_as_its_english_twin_does(text: str) -> None:
    intent = composer_image_intent(text, [])
    assert intent.request is not None, text


def test_a_look_is_not_a_picture_part() -> None:
    assert not plan_turn("Pinta bien, y dime qué más necesitas").of_kind("image")


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        ("Pinta un gato", "gato"),
        ("Pinte um gato", "gato"),
        # What a picture is for is not its subject ("draw a cat for my project").
        ("Dibuja un gato para mi proyecto", "gato para mi proyecto"),
    ],
)
def test_still_drawn(text: str, subject: str) -> None:
    assert extract_image_gen_prompt(text) == subject


@pytest.mark.parametrize(
    ("text", "prefer", "lang"),
    [
        ("Pinte um gato", "pt", "pt"),
        ("Pinte um gato", "es", "pt"),
        ("Pinte um gato", None, "pt"),
        ("Pinta un gato", "pt", "es"),
        # Nothing only one of them writes: the app's language, then Spanish.
        ("Ilustra gatos", "pt", "pt"),
        ("Ilustra gatos", None, "es"),
    ],
)
def test_a_shared_verb_follows_the_wording_then_the_app(
    text: str, prefer: str | None, lang: str
) -> None:
    assert picture_language(text, prefer) == lang


_AFTER_A_PICTURE = [
    SimpleNamespace(role="user", content="Generate image: black cat"),
    SimpleNamespace(
        role="assistant", content="[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]"
    ),
]


@pytest.mark.parametrize(
    "text",
    [
        "Zeichne das größer",
        "Zeichne das in Blau",
        "Zeichne die noch größer",
        "Zeichne den in Rot",
        "Dessine-la plus grande",
        "Dessine le en bleu",
        "Zeichne es größer",
        "Dibuja eso más grande",
    ],
)
def test_that_bigger_revises_the_last_picture(text: str) -> None:
    """As English "draw that bigger": an edit of the black cat, not a picture of "das größer"."""
    request = image_gen_request(text, _AFTER_A_PICTURE)
    assert request is not None and request.revision
    assert request.prompt.startswith("black cat")


@pytest.mark.parametrize(
    ("text", "subject"),
    [("Zeichne die Sonne", "die Sonne"), ("Dessine la tour Eiffel", "la tour Eiffel")],
)
def test_an_article_before_a_noun_is_a_new_picture(text: str, subject: str) -> None:
    request = image_gen_request(text, _AFTER_A_PICTURE)
    assert request is not None and not request.revision and request.prompt == subject


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


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        # "And then" in every language (English "… and then draw …" is not cut: a gain).
        ("Explique a fotossíntese e depois desenhe um girassol", "girassol"),
        ("Объясни фотосинтез, а потом нарисуй подсолнух", "подсолнух"),
        ("Объясни фотосинтез, затем нарисуй подсолнух", "подсолнух"),
        ("Fotosentezi açıkla, sonra bir ayçiçeği çiz", "ayçiçeği"),
        ("Explica la fotosíntesis y después dibuja un girasol", "girasol"),
    ],
)
def test_and_then_draw_is_a_picture_part(text: str, subject: str) -> None:
    plan = plan_turn(text)
    assert [part.kind for part in plan.parts] == ["ask", "image"]
    assert extract_image_gen_prompt(plan.of_kind("image")[0].text) == subject
