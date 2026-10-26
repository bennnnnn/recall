"""A picture asked in another language draws only things on the language's list.

Review 5 found a third of its task-style draw-me lines drawn as pictures under the old
block-list ("Dibújame un cuadro comparativo", "Zeichne mir einen Grundriss", "Нарисуй
мне сказку на ночь"). Now the subject's head noun must be a listed concrete thing.
``language_pictures.json`` holds everyday requests that must still draw: review 5's
positives and round 6's, written before and after its blind run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.images.gen_intent import extract_image_gen_prompt
from app.modules.images.gen_intent_drawable import NOUNS, names_drawable
from app.modules.images.gen_intent_parts import picture_language
from app.modules.images.intent import composer_image_intent

_PICTURES: dict[str, list[str]] = json.loads(
    Path(__file__).with_name("language_pictures.json").read_text(encoding="utf-8")
)
PICTURES = [(lang, text) for lang, texts in _PICTURES.items() for text in texts]


@pytest.mark.parametrize(("lang", "text"), PICTURES)
def test_an_everyday_picture_still_draws(lang: str, text: str) -> None:
    assert composer_image_intent(text, []).request is not None
    assert picture_language(text) == lang


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        # The head comes after a size, a look, a number or "my".
        ("Dibújame dos gatitos", "dos gatitos"),
        ("Dibújame mi casa", "mi casa"),
        ("Dessine-moi un petit chat", "petit chat"),
        ("Disegnami un bel tramonto", "bel tramonto"),
        ("Me desenhe um pôr do sol", "pôr do sol"),
        ("Dibujame un leon", "leon"),
        # German: an adjective before the noun, a compound ending in a listed noun.
        ("Zeichne mir einen süßen Hund mit Hut", "süßen Hund mit Hut"),
        ("zeichne mir einen süßen hund", "süßen hund"),
        ("Zeichne mir einen Feuerdrachen", "Feuerdrachen"),
        ("Zeichne mir ein Piratenschiff", "Piratenschiff"),
        # Russian: adjectives and cases; "with" in a create-of request.
        ("Нарисуй мне белого медведя", "белого медведя"),
        ("Нарисуй мне божью коровку", "божью коровку"),
        ("Создай картинку с котом", "с котом"),
        # Turkish and Amharic close with the head; compound forms.
        ("Bana bir kutup ayısı çiz", "kutup ayısı"),
        ("Bana bir ayı çiz", "ayı"),
        ("Bana bir gün batımı çiz", "gün batımı"),
        ("Bana bir uzay gemisi çiz", "uzay gemisi"),
        ("ኮፍያ ያደረገች ድመት ሳልልኝ", "ኮፍያ ያደረገች ድመት"),
    ],
)
def test_the_head_noun_is_found(text: str, subject: str) -> None:
    assert extract_image_gen_prompt(text) == subject


@pytest.mark.parametrize(
    "text",
    [
        # Not on any list: a table, a plan, a story, a portrait, a map, the future.
        "Dibújame un cuadro comparativo entre iPhone y Android",
        "Zeichne mir einen Grundriss meiner Wohnung",
        "Нарисуй мне сказку на ночь",
        "Bana bir uyku masalı çiz",
        "Dibújame un retrato de mi gato",
        "Dibújame un mapa del tesoro",
        "Dessine-moi un avenir meilleur",
        # A German compound whose last part is listed but is no picture.
        "Zeichne mir einen Muskelkater",
        "Zeichne mir eine Eselsbrücke",
        "Zeichne mir einen Stammbaum",
        "Zeichne mir eine Glühlampe",
        # A capitalised German noun before the head is a noun, not an adjective.
        "Zeichne mir eine Tabelle mit Katzen",
        # Russian "-ние" nouns are no adjectives: "строение" is no look of a flower.
        "Нарисуй мне строение цветка",
        # A listed head with a blocked word after it, or a family tree.
        "Dibújame un gato con una tabla de multiplicar",
        "Dibújame un volcán con sus partes",
        "Zeichne mir eine Blume mit ihren Teilen",
        "Нарисуй мне дерево вероятностей",
        "Bana bir soy ağacı çiz",
        "የቤተሰብ ዛፍ ሳልልኝ",
        # Definite in Turkish: the bear, the lion.
        "Bana ayıyı çiz",
        "Bana aslanı çiz",
    ],
)
def test_a_subject_without_a_listed_head_is_answered(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
    assert composer_image_intent(text, []).request is None


@pytest.mark.parametrize("code", sorted(NOUNS))
def test_every_language_lists_its_common_things(code: str) -> None:
    """About 300 to 450 entries a language (Amharic fewer: only the sure words)."""
    nouns = NOUNS[code]
    assert len(nouns.entries) >= (120 if code == "am" else 350)


@pytest.mark.parametrize(
    ("code", "words"),
    [
        ("es", ["mapa"]),
        ("es", ["planta"]),
        ("fr", ["tableau"]),
        ("de", ["Herz"]),
        ("it", ["piano"]),
        ("pt", ["planta"]),
        ("ru", ["схему"]),
        ("tr", ["harita"]),
        ("am", ["ካርታ"]),
    ],
)
def test_task_and_school_nouns_are_not_listed(code: str, words: list[str]) -> None:
    assert not names_drawable(code, [word.lower() for word in words], words)
