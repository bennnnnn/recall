"""Picture requests in the app's other languages: only the unmistakable shapes draw.

"Dibújame un gato con sombrero" drew nothing on main: every rule read English words.
Now a draw verb addressed with "me" ("dibújame", "¿me dibujas …?", "нарисуй мне", "bana …
çiz", "… ሳልልኝ", "मेरे लिए … ड्रा करो") and "create a picture of" ("crea una imagen de",
"… की तस्वीर बनाओ", "एक … का चित्र बनाओ") draw a short, plain subject whose every word is
listed (``test_gen_intent_drawable``), when that request is the whole message. Everything
else in those languages is answered in words, as on main.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.gen_intent import extract_image_gen_prompt
from app.modules.images.gen_intent_languages import LANGUAGES
from app.modules.images.gen_intent_local import _read, _tokens_of
from app.modules.images.intent import composer_image_intent, image_gen_request


def read_in(text: str) -> list[str]:
    """The languages whose shapes read ``text`` as one picture request, in reading order."""
    tokens = _tokens_of(text)
    return [lang.code for lang in LANGUAGES if _read(lang, text, tokens)]


# At least six common requests per language, with the subject drawn.
DRAWN: dict[str, list[tuple[str, str]]] = {
    "es": [
        ("Dibújame un dragón", "dragón"),
        ("¿Me dibujas un dragón?", "dragón"),
        ("Dibújame un gato con sombrero", "gato con sombrero"),
        ("Píntame un atardecer en la playa", "atardecer en la playa"),
        ("¿Puedes dibujarme un unicornio?", "unicornio"),
        ("¿Me puedes dibujar un castillo?", "castillo"),
        ("Crea una imagen de un león", "león"),
        ("Genera una ilustración de un bosque mágico", "bosque mágico"),
    ],
    "fr": [
        ("Dessine-moi un mouton", "mouton"),
        ("Tu peux me dessiner un chat ?", "chat"),
        ("Peux-tu me dessiner un dragon ?", "dragon"),
        ("Dessinez-moi une maison dans la forêt", "maison dans la forêt"),
        ("Tu me dessines un panda ?", "panda"),
        ("Génère une image d'un lion", "lion"),
        ("Crée une illustration d'une forêt magique", "forêt magique"),
    ],
    "pt": [
        ("Desenha-me um gato", "gato"),
        ("Me desenhe um cachorro", "cachorro"),
        ("Pode me desenhar um dragão?", "dragão"),
        ("Você pode me desenhar um unicórnio?", "unicórnio"),
        ("Me desenha um castelo nas nuvens", "castelo nas nuvens"),
        ("Crie uma imagem de um leão", "leão"),
        ("Gere uma ilustração de uma floresta mágica", "floresta mágica"),
    ],
    "ru": [
        ("Нарисуй мне собаку", "собаку"),
        ("Нарисуй мне единорога", "единорога"),
        ("Можешь нарисовать мне кота?", "кота"),
        ("Нарисуйте мне замок в облаках", "замок в облаках"),
        ("Можешь мне нарисовать дракона?", "дракона"),
        ("Создай изображение льва", "льва"),
        ("Сгенерируй картинку замка в облаках", "замка в облаках"),
    ],
    "tr": [
        ("Bana bir panda çizer misin?", "panda"),
        ("Bana bir kedi çiz", "kedi"),
        ("Bana şapkalı bir kedi çiz", "şapkalı bir kedi"),
        ("Bana bir ejderha çizebilir misin?", "ejderha"),
        ("Bana bir unicorn çiz lütfen", "unicorn"),
        ("Bir aslan resmi oluştur", "aslan"),
        ("Büyülü bir orman görseli oluştur", "Büyülü bir orman"),
    ],
    "am": [
        ("ድመት ሳልልኝ", "ድመት"),
        ("የዘንዶ ስዕል ሳልልኝ", "ዘንዶ"),
        ("እባክህ ድመት ሳልልኝ", "ድመት"),
        ("የአንበሳ ምስል ፍጠር", "አንበሳ"),
        ("የአበባ ምስል ፍጠርልኝ", "አበባ"),
        ("ፈረስ ሳልልኝ", "ፈረስ"),
    ],
    "hi": [
        ("मेरे लिए बिल्ली का चित्र बनाओ", "बिल्ली"),
        ("एक बिल्ली का चित्र बनाओ", "बिल्ली"),
        ("मेरे लिए एक काली बिल्ली ड्रा करो", "काली बिल्ली"),
        ("कृपया एक ड्रैगन की तस्वीर बनाइए", "ड्रैगन"),
        ("मेरे लिए एक शेर का चित्र बना दो", "शेर"),
        ("एक घोड़ा ड्रा करो", "घोड़ा"),
        ("जंगल में एक हाथी की पेंटिंग बनाइए", "जंगल में एक हाथी"),
    ],
}
DRAWN_CASES = [(lang, text, subject) for lang, cases in DRAWN.items() for text, subject in cases]

# On main and now, answered in words: no "me", no picture noun with "of", a definite or
# pointing-back subject, a long or numeric one, the "illustrate" verbs, Turkish and
# Amharic without "bana" / "ልኝ", lines in German and Italian (no app language), a photo.
ANSWERED = [
    "Dibuja un gato",
    "Dibuja un gato con sombrero",
    "Zeichne eine Katze mit Hut",
    "Male eine Katze",
    "Dessine un chat",
    "Disegna un gatto",
    "Desenhe um gato com chapéu",
    "Нарисуй кошку",
    "Şapkalı bir kedi çiz",
    "Bir kedi çizer misin?",
    "የድመት ስዕል ሳል",
    "Ilustra un bosque",
    "Illustrami un drago",
    "Genera una foto di un gatto",
    "Crea una imagen realista de un león",
    "Me desenhe o Pikachu",
    "Dessine-moi la tour Eiffel",
    "Zeichne mir den Mond",
    "Bana kediyi çiz",
    "Zeichne mir das größer",
    "Dibújame eso otra vez",
    "Нарисуй мне это ещё раз",
    "Dibújame un gato con 3 colas",
    "Dibújame un gato grande negro con un sombrero rojo enorme",
    "Dibújame y = x^2",
    "Zeichne mir Ethanol",
    # Hindi: "बनाओ" without a picture word also cooks, builds and plans; a school figure.
    # A bare "<noun> का चित्र बनाइए" is how a textbook asks for its figure, and a bare draw
    # verb is "Dibuja un gato": neither is addressed nor names a new thing with "एक".
    "बिल्ली बनाओ",
    "बिल्ली का चित्र बनाओ",
    "बिल्ली ड्रा करो",
    "फूल का चित्र बनाइए",
    "ज्वालामुखी का चित्र बनाइए",
    "पत्ते का चित्र बनाइए",
    "ग्रह का चित्र बनाइए",
    "इंद्रधनुष का चित्र बनाइए",
    "बादल का चित्र बनाइए",
    "नदी का चित्र बनाइए",
    "मेरे लिए चाय बनाओ",
    "मेरे लिए एक योजना बनाओ",
    "इसका चित्र बनाओ",
    "त्रिभुज का चित्र बनाओ",
    "प्रकाश संश्लेषण का चित्र बनाओ",
    "फिर से बिल्ली का चित्र बनाओ",
]


@pytest.mark.parametrize(("lang", "text", "subject"), DRAWN_CASES)
def test_a_draw_me_or_create_request_draws(lang: str, text: str, subject: str) -> None:
    assert extract_image_gen_prompt(text) == subject
    assert read_in(text)[:1] == [lang]


@pytest.mark.parametrize(("lang", "text", "subject"), DRAWN_CASES)
def test_the_composer_draws_it_as_the_chat_turn_would(lang: str, text: str, subject: str) -> None:
    intent = composer_image_intent(text, [])
    assert intent.lookup_query is None
    assert intent.request is not None and intent.request.prompt == subject, lang


@pytest.mark.parametrize("text", ANSWERED)
def test_other_shapes_are_answered_in_words(text: str) -> None:
    assert composer_image_intent(text, []).request is None
    assert not plan_turn(text).of_kind("image")


# A draw-me picture beside a second request, either order. English cuts "draw me a cat and
# also explain …" into a picture and an answer; in the other languages a line beside a
# draw-me line is often about it ("¿Cómo se dice en inglés? Dibújame un gato", "Dime si
# es educado. Dibújame un gato"), so no such message is cut: it is answered, as on main.
WITH_A_SECOND_REQUEST = [
    "Dibújame un gato con sombrero y también explica qué es un agujero negro",
    "Dessine-moi un chat et explique aussi ce qu'est un trou noir",
    "Zeichne mir eine Katze mit Hut und erkläre auch, was ein schwarzes Loch ist",
    "Disegnami un gatto e spiega anche cos'è un buco nero",
    "Me desenhe um gato e também explique o que é um buraco negro",
    "Bana şapkalı bir kedi çiz ve ayrıca kara deliğin ne olduğunu açıkla",
    "Нарисуй мне кошку, а также объясни, что такое чёрная дыра",
    "ድመት ሳልልኝ እንዲሁም ጥቁር ቀዳዳ ምን እንደሆነ አስረዳኝ",
    "Zeichne mir eine Katze and also explain what a black hole is",
    "Explica qué es un agujero negro y dibújame un gato",
    "¿Qué es un agujero negro? Dibújame un gato",
    "Quelle est la capitale de l'Italie ? Dessine-moi un chat",
    "Erkläre, was ein schwarzes Loch ist, und kannst du mir eine Katze malen?",
    "Kara deliğin ne olduğunu açıkla ve bana bir kedi çiz",
    "Объясни фотосинтез, а потом нарисуй мне подсолнух",
    "Dibújame un perro y dime cuánto vive",
]


@pytest.mark.parametrize("text", WITH_A_SECOND_REQUEST)
def test_a_draw_me_line_beside_a_second_request_is_answered(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
    assert composer_image_intent(text, []).request is None
    assert not plan_turn(text).of_kind("image")


@pytest.mark.parametrize(
    "text",
    [
        # The picture clause is no narrow shape: one answer, no picture part.
        "Dibuja un gato con sombrero y también explica qué es un agujero negro",
        "Explica qué es un agujero negro y dibuja un gato",
        "Zeichne eine Katze und erkläre, was ein schwarzes Loch ist",
        "Нарисуй кошку и объясни, что такое чёрная дыра",
    ],
)
def test_a_broad_picture_clause_beside_a_question_is_one_answer(text: str) -> None:
    assert not plan_turn(text).of_kind("image")


@pytest.mark.parametrize(
    "text",
    [
        "Dibújame un gato y un perro",
        "Dessine-moi un chat qui danse",
        "एक बिल्ली और एक कुत्ते का चित्र बनाओ",
    ],
)
def test_a_longer_picture_is_still_one_picture(text: str) -> None:
    assert extract_image_gen_prompt(text)


@pytest.mark.parametrize(
    "text",
    [
        "«Dibújame un cordero»: ¿quién lo dijo?",
        "„Zeichne mir ein Schaf“: Wer hat das gesagt?",
        "« Dessine-moi un mouton » : qui a dit ça ?",
        "'Bana bir kuzu çiz' sözü kimin?",
        "「ድመት ሳልልኝ」 ማን አለ?",
        # A quoted request alone is a quotation too.
        "«Dibújame un gato»",
        "'Dibújame un gato'",
        "\u2018Dibújame un gato\u2019",
        "Zeichne mir eine „Katze“",
    ],
)
def test_a_quoted_line_is_no_request(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
    assert not plan_turn(text).of_kind("image")


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        ("Crée une image d'un dragon rouge", "dragon rouge"),
        ("Crée une image d\u2019un dragon rouge", "dragon rouge"),
        ("Dessine-moi un gâteau d'anniversaire", "gâteau d'anniversaire"),
    ],
)
def test_an_apostrophe_inside_a_word_is_no_quote(text: str, subject: str) -> None:
    assert extract_image_gen_prompt(text) == subject


# Main's readings of 374 English prompts from the sweep, STEM corpus, battery and intent
# fixture: every one main drew (141) and every 20th of the rest. Recorded on origin/main.
_ENGLISH_ON_MAIN: dict[str, dict[str, str | None]] = json.loads(
    (Path(__file__).with_name("english_main_readings.json")).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("text", sorted(_ENGLISH_ON_MAIN))
def test_english_reads_as_on_main(text: str) -> None:
    """The other languages are read only after every English rule declined."""
    request = image_gen_request(text, [])
    assert extract_image_gen_prompt(text) == _ENGLISH_ON_MAIN[text]["extract"]
    assert (request.prompt if request else None) == _ENGLISH_ON_MAIN[text]["request"]


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        # Drawn on main, and still: the words after "and" describe the picture.
        ("draw me a dog and write Max on its collar", "dog and write Max on its collar"),
        ("draw me a cat and show it sleeping", "cat and show it sleeping"),
        ("draw me a robot and tell me its name", "robot and tell me its name"),
        ("draw me a cat and then show me a dog", "cat and then show me a dog"),
        # Main's plan does not cut "… and how are you": the whole line is the picture.
        ("draw me a cat and how are you", "cat and how are you"),
        ("draw me a castle and help", "castle and help"),
    ],
)
def test_english_draw_me_with_a_picture_detail_draws_as_on_main(text: str, subject: str) -> None:
    assert extract_image_gen_prompt(text) == subject


@pytest.mark.parametrize(
    "text",
    [
        "draw me a cat and also explain black holes",
        "draw me a cat and explain what a black hole is",
        "draw me a cat and tell me what a black hole is",
        "draw me a cat and how do magnets work",
        "draw me a cat, and also explain black holes",
        "draw me a cat and also show me a dog",
    ],
)
def test_english_draw_me_with_a_second_request_draws_only_the_picture_part(text: str) -> None:
    """Main drew the whole line ("cat and also explain black holes") although its plan
    split it; now the plan's picture part is drawn beside the answer."""
    assert extract_image_gen_prompt(text) is None
    plan = plan_turn(text)
    assert plan.parts[0].kind == "image" and plan.parts[0].text.startswith("draw me a cat")


@pytest.mark.parametrize(
    "text",
    [
        # ड़ and ज़ typed as one sign (U+095C, U+095B) or as the letter and its dot.
        "मेरे लिए एक घोड़ा ड्रा करो",
        "मेरे लिए एक घोड़ा ड्रा करो",
        "प्लीज़ मेरे लिए एक घोड़ा ड्रा करो",
        "प्लीज़ मेरे लिए एक घोड़ा ड्रा करो",
    ],
)
def test_a_dotted_hindi_letter_reads_either_way(text: str) -> None:
    assert extract_image_gen_prompt(text) == "घोड़ा"
