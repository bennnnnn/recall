"""A draw-me line the user asks about, not for, draws nothing (review 7, 1A and 1B).

"Traduce al inglés: dibújame un gato" asks for the line in English, "¿Cómo se dice en
inglés? Dibújame un gato" how to say it, "«Dibújame un cordero»: ¿quién lo dijo?" who said
it. English answers its twins on main with no picture: a quote is never cut, "translate
…:" keeps the message whole, and a first clause that points ("Is this sentence correct?")
keeps it whole. A picture asked second is cut off only after a request of its own:
"¿Qué es un agujero negro? Dibújame un gato" still draws the cat beside the answer.
"""

from __future__ import annotations

import pytest

from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.gen_intent import extract_image_gen_prompt
from app.modules.images.gen_intent_parts import Part, picture_and_request, picture_language
from app.modules.images.gen_intent_wording import has_colon, quoted


def _no_picture(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
    assert picture_and_request(text) is None
    assert not plan_turn(text).of_kind("image")


@pytest.mark.parametrize(
    "text",
    [
        "«Dibújame un cordero»: ¿quién lo dijo?",
        "„Zeichne mir ein Schaf“: Wer hat das gesagt?",
        "«Нарисуй мне барашка»: кто это сказал?",
        "« Dessine-moi un mouton » : qui a dit ça ?",
        '"Disegnami una pecora": chi l\'ha detto?',
        "“Desenha-me um carneiro” — quem disse isso?",
        "'Bana bir kuzu çiz' sözü kimin?",
        "‹Dibújame un gato› en inglés",
        "「ድመት ሳልልኝ」 ማን አለ?",
        # A quoted request alone is still a quotation, not a request.
        "«Dibújame un gato»",
        "„Zeichne mir eine Katze“",
        "Dibújame un 'gato'",
    ],
)
def test_a_quoted_line_is_no_request(text: str) -> None:
    assert quoted(text)
    _no_picture(text)


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        ("Crée une image d'un dragon rouge", "dragon rouge"),
        ("Crée une image d’un dragon rouge", "dragon rouge"),
        ("Crea un'immagine di un castello incantato", "castello incantato"),
        ("Dessine-moi un gâteau d'anniversaire", "gâteau d'anniversaire"),
    ],
)
def test_an_apostrophe_inside_a_word_is_no_quote(text: str, subject: str) -> None:
    assert not quoted(text)
    assert extract_image_gen_prompt(text) == subject


@pytest.mark.parametrize(
    "text",
    [
        "Traduce al inglés: dibújame un gato",
        "Traduce:\nDibújame un gato",
        "Dime qué significa: dibújame un gato",
        "Traduis en anglais : dessine-moi un mouton",
        "Traduis en anglais: dessine-moi un chat",
        "Übersetze ins Englische: Zeichne mir eine Katze",
        "Sag mir, was das heißt: Zeichne mir eine Katze",
        "Traduci in inglese: disegnami un gatto",
        "Traduza para o inglês: desenha-me um gato",
        "Переведи на английский: нарисуй мне кота",
        "İngilizceye çevir: bana bir kedi çiz",
        "ወደ እንግሊዝኛ ተርጉም፦ ድመት ሳልልኝ",
        # Any ask before a colon: what follows is the text it asks about.
        "Analiza sintácticamente: dibújame un gato",
        "Explique la grammaire de : dessine-moi un chat",
        "Dibújame un cordero: ¿quién lo dijo?",
    ],
)
def test_a_line_with_a_colon_is_never_cut(text: str) -> None:
    assert has_colon(text)
    _no_picture(text)


def test_a_time_is_no_colon() -> None:
    assert not has_colon("Dibújame un gato y dime qué pasa a las 10:30")
    assert has_colon("Pregunta: dibújame un gato")


@pytest.mark.parametrize(
    "text",
    [
        # Wording, spelling, pronunciation, grammar, meaning, translation.
        "¿Cómo se dice en inglés? Dibújame un gato",
        "¿Está bien escrito? Dibújame un caballo",
        "¿Esta frase es correcta? Dibújame un gato",
        "¿Cuántas palabras tiene? Dibújame un gato negro",
        "¿Qué quiere decir? Dibújame un barco",
        "¿Cuál es el sujeto? Dibújame un gato",
        "¿Cómo es en inglés? Dibújame un gato",
        "Comment on dit ça en anglais? Dessine-moi un chat",
        "Comment dit-on en anglais ? Dessine-moi un chat",
        "Quel est le verbe dans cette phrase ? Dessine-moi un chat",
        "Ist dieser Satz richtig? Zeichne mir eine Katze",
        "Wie sagt man das auf Englisch? Zeichne mir eine Katze",
        "Was ist das Subjekt? Zeichne mir eine Katze",
        "Come si dice in inglese? Disegnami un gatto",
        "Questa frase è corretta? Disegnami un gatto",
        "Como se diz em inglês? Desenha-me um gato",
        "Qual é o contrário? Desenha-me um gato",
        "Как сказать по-английски? Нарисуй мне кота",
        "Это предложение правильное? Нарисуй мне кота",
        "İngilizcede nasıl denir? Bana bir kedi çiz",
        "Bu cümle doğru mu? Bana bir kedi çiz",
        "በእንግሊዝኛ እንዴት ይባላል? ድመት ሳልልኝ",
        "ይህ ዓረፍተ ነገር ትክክል ነው? ድመት ሳልልኝ",
        "How do you pronounce this? Zeichne mir eine Katze",
        # Figures of speech, tense and case, a joke, "how is my Spanish?".
        "¿Qué figura retórica es? Dibújame un gato",
        "Quelle figure de style est-ce ? Dessine-moi un mouton",
        "Welche Zeitform? Zeichne mir eine Katze",
        "Какой падеж? Нарисуй мне кота",
        "Explica el chiste. Dibújame un gato",
        "¿Qué tal mi español? Dibújame un gato",
        "How is my Spanish? Dibújame un gato",
        # Attribution.
        "¿Quién es el autor? Dibújame un cordero",
        "¿Qué libro es? Dibújame un cordero",
        "Wer hat das geschrieben? Zeichne mir ein Schaf",
        "Кто автор? Нарисуй мне барашка",
        # Translate, then the picture: the line is what to translate.
        "Traduis en anglais et dessine-moi un chat",
        "Переведи на английский и нарисуй мне кота",
        "İngilizceye çevir ve bana bir kedi çiz",
        # A question with nothing of its own, or no question at all.
        "¿Qué? Dibújame un gato",
        "¿Por qué? Dibújame un gato",
        "Was ist das? Zeichne mir eine Katze",
        "Me encantan los gatos. Dibújame un gato",
    ],
)
def test_a_picture_after_an_ask_about_it_is_not_cut(text: str) -> None:
    _no_picture(text)


@pytest.mark.parametrize(
    "text",
    [
        "Dibújame un gato. ¿Cómo se dice en francés?",
        "Dibújame un gato. ¿Cuál es el sujeto?",
        "Dessine-moi un mouton. Comment on dit ça en anglais ?",
        "Zeichne mir ein Schaf. Wie sagt man das auf Französisch?",
        "Нарисуй мне барашка. Кто автор?",
        "Bana bir kuzu çiz. Yazarı kim?",
        "Dessine-moi un chat. Comment est mon français ?",
        "Dibújame un gato y dime qué figura retórica usa",
        "በግ ሳልልኝ። በእንግሊዝኛ እንዴት ይባላል?",
    ],
)
def test_a_question_about_the_picture_line_after_it_is_not_cut(text: str) -> None:
    _no_picture(text)


@pytest.mark.parametrize(
    ("text", "ask", "picture"),
    [
        (
            "¿Qué es un agujero negro? Dibújame un gato",
            "¿Qué es un agujero negro?",
            "Dibújame un gato",
        ),
        (
            "Quelle est la capitale de l'Italie ? Dessine-moi un chat",
            "Quelle est la capitale de l'Italie ?",
            "Dessine-moi un chat",
        ),
        (
            "Was ist ein schwarzes Loch? Zeichne mir eine Katze",
            "Was ist ein schwarzes Loch?",
            "Zeichne mir eine Katze",
        ),
        (
            "Resume la Revolución Francesa y dibújame un caballo",
            "Resume la Revolución Francesa",
            "dibújame un caballo",
        ),
        (
            "Kara delik nedir? Bana bir kedi çiz",
            "Kara delik nedir?",
            "Bana bir kedi çiz",
        ),
    ],
)
def test_a_request_of_its_own_then_a_picture_is_cut(text: str, ask: str, picture: str) -> None:
    """A language's name names a language only after "in", "into", "to": "la Revolución
    Francesa" asks about history, and French " ?" ends a sentence as "?" does."""
    assert picture_and_request(text) == (Part(ask, picture=False), Part(picture, picture=True))
    assert [part.kind for part in plan_turn(text).parts] == ["ask", "image"]
    assert picture_language(picture) is not None
