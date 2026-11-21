"""A picture asked in another language draws only a subject made of listed words.

Review 5 found a third of its task-style draw-me lines drawn under the old block-list
("Dibújame un cuadro comparativo", "Zeichne mir einen Grundriss"). Round 6 listed the
head noun; review 6 then found 170 of 207 lines drawn through what followed a listed
head ("un gato en ASCII", "un árbol binario", "un puente de Wheatstone", "un perro y
sugiéreme nombres"). Now every word of the subject must be a listed noun, a plain
descriptor or a function word. ``language_pictures.json`` holds everyday requests that
must still draw.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.images.gen_intent import extract_image_gen_prompt
from app.modules.images.gen_intent_drawable import DESCRIBE, GLUE, NOUNS, names_drawable
from app.modules.images.intent import composer_image_intent
from app.tests.modules.images.test_gen_intent_languages import read_in

_PICTURES: dict[str, list[str]] = json.loads(
    Path(__file__).with_name("language_pictures.json").read_text(encoding="utf-8")
)
PICTURES = [(lang, text) for lang, texts in _PICTURES.items() for text in texts]


@pytest.mark.parametrize(("lang", "text"), PICTURES)
def test_an_everyday_picture_still_draws(lang: str, text: str) -> None:
    assert composer_image_intent(text, []).request is not None
    assert read_in(text)[:1] == [lang]


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        # Sizes, looks, numbers and "my" before the noun; colours, places and poses after.
        ("Dibújame dos gatitos", "dos gatitos"),
        ("Dibújame mi casa", "mi casa"),
        ("Dibújame un gato negro en la playa", "gato negro en la playa"),
        ("Dibújame un unicornio con alas", "unicornio con alas"),
        ("Dibújame un perro y un gato", "perro y un gato"),
        ("Dessine-moi un petit chat", "petit chat"),
        ("Dessine-moi un chat qui joue du piano", "chat qui joue du piano"),
        ("Me desenhe um pôr do sol", "pôr do sol"),
        ("Me desenhe um cachorro de óculos", "cachorro de óculos"),
        ("Dibujame un leon", "leon"),
        # Russian: adjective and noun cases made from the listed forms.
        ("Нарисуй мне белого медведя", "белого медведя"),
        ("Нарисуй мне божью коровку", "божью коровку"),
        ("Создай картинку с котом", "с котом"),
        ("Нарисуйте мне замок в облаках", "замок в облаках"),
        ("Нарисуй мне принцессу в замке", "принцессу в замке"),
        # Turkish closes with the noun; "with", "in" and compound forms are made.
        ("Bana bir kutup ayısı çiz", "kutup ayısı"),
        ("Bana bir ayı çiz", "ayı"),
        ("Bana bir gün batımı çiz", "gün batımı"),
        ("Bana bir uzay gemisi çiz", "uzay gemisi"),
        ("Bana şapkalı bir kedi çiz", "şapkalı bir kedi"),
        ("Bulutlarda bir kale resmi oluştur", "Bulutlarda bir kale"),
        ("Gün batımında bir aslan resmi oluştur", "Gün batımında bir aslan"),
        ("ቀይ መኪና ሳልልኝ", "ቀይ መኪና"),
        # Hindi closes with the noun; an adjective agrees with it ("काला" → काली, काले).
        ("मेरे लिए एक काली बिल्ली ड्रा करो", "काली बिल्ली"),
        ("मेरे लिए काले घोड़े का चित्र बनाओ", "काले घोड़े"),
        ("लाल टोपी वाली बिल्ली की तस्वीर बनाइए", "लाल टोपी वाली बिल्ली"),
        ("मेरे लिए समुद्र तट पर सूर्यास्त का चित्र बनाओ", "समुद्र तट पर सूर्यास्त"),
        ("एक बिल्ली और एक कुत्ते का चित्र बनाओ", "बिल्ली और एक कुत्ते"),
    ],
)
def test_a_subject_of_listed_words_draws(text: str, subject: str) -> None:
    assert extract_image_gen_prompt(text) == subject


@pytest.mark.parametrize(
    "text",
    [
        # Not on any list: a table, a plan, a story, a portrait, a map, the future.
        "Dibújame un cuadro comparativo entre iPhone y Android",
        "Нарисуй мне сказку на ночь",
        "Bana bir uyku masalı çiz",
        "Dibújame un retrato de mi gato",
        "Dibújame un mapa del tesoro",
        "Dessine-moi un avenir meilleur",
        "Dibújame una ciudad del futuro",
        "Нарисуй мне строение цветка",
        # Definite in Turkish: the bear, the lion.
        "Bana ayıyı çiz",
        "Bana aslanı çiz",
        # Something more than a picture said with a verb: answered, not drawn.
        "ኮፍያ ያደረገች ድመት ሳልልኝ",
        # Hindi: a map, a plan, a family tree, a flower's parts.
        "मेरे लिए भारत के नक्शे का चित्र बनाओ",
        "मेरे लिए मेरे घर के नक्शे का चित्र बनाओ",
        "मेरे लिए परिवार के पेड़ का चित्र बनाओ",
        "मेरे लिए फूल के भागों का चित्र बनाओ",
    ],
)
def test_a_subject_with_an_unlisted_noun_is_answered(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
    assert composer_image_intent(text, []).request is None


@pytest.mark.parametrize(
    "text",
    [
        # Text or code asked for as a drawing.
        "Dibújame un gato en ASCII",
        "Dessine-moi un chat en SVG",
        "Desenha-me um gato em LaTeX",
        "Нарисуй мне кота символами",
        "Bana ASCII ile bir kedi çiz",
        "በASCII ድመት ሳልልኝ",
        "मेरे लिए ASCII में बिल्ली का चित्र बनाओ",
        # Data structures and circuits on a listed tree, forest or bridge.
        "Dibújame un árbol binario",
        "Dessine-moi une forêt aléatoire",
        "Нарисуй мне красно-чёрное дерево",
        "Нарисуй мне диодный мост",
        "Bana bir ikili ağaç çiz",
        "Dibújame un puente de Wheatstone",
        # Maths and physics on an everyday noun; figures of speech.
        "Dibújame una pizza dividida en fracciones",
        "Dessine-moi une étoile dans un repère orthonormé",
        "Dibújame un gato con una tabla de multiplicar",
        "Dibújame un volcán con sus partes",
        "Нарисуй мне дерево вероятностей",
        "Dibújame una montaña de deudas",
        "Bana bir soy ağacı çiz",
        "የቤተሰብ ዛፍ ሳልልኝ",
    ],
)
def test_a_listed_noun_with_an_unlisted_word_is_answered(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
    assert composer_image_intent(text, []).request is None


@pytest.mark.parametrize(
    "text",
    [
        "Dibújame un perro y sugiéreme nombres",
        "Dessine-moi un chien et propose-moi des noms",
        "Desenha-me um cachorro e sugira nomes",
        "Нарисуй мне собаку и придумай ей имя",
        "Bana bir köpek çiz ve isim öner",
        "ውሻ ሳልልኝና ስም ጠቁመኝ",
        "मेरे लिए कुत्ते का चित्र बनाओ और उसका नाम सुझाओ",
    ],
)
def test_a_second_request_after_the_picture_is_answered(text: str) -> None:
    """The second request is not swallowed into the picture's subject: the line is answered."""
    assert extract_image_gen_prompt(text) is None
    assert composer_image_intent(text, []).request is None


@pytest.mark.parametrize(
    ("code", "words"),
    [
        # "and" joins two drawable nouns, never a describing word alone.
        ("es", ["árbol", "rojo", "y", "negro"]),
        ("es", ["gato", "y"]),
        # A subject ends on a noun or a describing word, never on "of" or "with".
        ("es", ["gato", "con"]),
        ("fr", ["chat", "de"]),
        # Turkish, Amharic and Hindi close with the noun.
        ("tr", ["kedi", "kırmızı"]),
        ("hi", ["बिल्ली", "काली"]),
        # A noun is needed: describing words alone draw nothing.
        ("hi", ["छोटी", "लाल"]),
    ],
)
def test_a_subject_needs_its_nouns_in_place(code: str, words: list[str]) -> None:
    assert not names_drawable(code, words)


@pytest.mark.parametrize("code", sorted(NOUNS))
def test_every_language_lists_its_common_things(code: str) -> None:
    """About 300 to 450 entries a language (Amharic and Hindi fewer: only the sure words)."""
    assert len(NOUNS[code].entries) >= {"am": 120, "hi": 300}.get(code, 350)
    assert DESCRIBE[code] and GLUE[code]


@pytest.mark.parametrize(
    ("code", "word"),
    [
        ("es", "mapa"),
        ("es", "planta"),
        ("fr", "tableau"),
        ("pt", "planta"),
        ("ru", "схему"),
        ("tr", "harita"),
        ("am", "ካርታ"),
        ("hi", "नक्शा"),
        ("hi", "योजना"),
    ],
)
def test_task_nouns_are_not_listed(code: str, word: str) -> None:
    assert not names_drawable(code, [word])


@pytest.mark.parametrize(
    ("code", "text", "words"),
    [
        ("es", "Dibújame un árbol binario", ["árbol", "binario"]),
        ("es", "Dibújame un gato en ASCII", ["gato", "en", "ascii"]),
        ("fr", "Dessine-moi un chat en ASCII", ["chat", "en", "ascii"]),
    ],
)
def test_format_and_data_structure_words_are_not_listed(
    code: str, text: str, words: list[str]
) -> None:
    """A lone descriptor never draws (a subject needs a noun), so each word is read beside
    a listed noun: the noun draws, the subject with the word does not."""
    assert any(names_drawable(code, [word]) for word in words)
    assert not names_drawable(code, words)
    assert extract_image_gen_prompt(text) is None
