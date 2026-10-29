"""Every misfire the seven reviews found, and the round-5 to round-8 probes: answered.

A misfire (a picture drawn where the user wanted words) costs a daily picture and the
answer. ``language_misfires.json`` holds each sentence a review named as drawn wrongly
(physics homework, plans, tables, algorithms, idioms, "Dibuja un ejemplo", "Mal den
Teufel nicht an die Wand", a Docker image…), the reviewers' non-picture probe lines,
the everyday lines with picture words written for round 5, most of them in a draw-me
shape ("Dibújame la pirámide alimenticia", "Zeichne mir einen Trainingsplan"), review 5's
task subjects ("Dibújame un cuadro comparativo", "Нарисуй мне сказку на ночь"), round
6's blind set and its drawable heads with task words ("un volcán con sus partes"), review
6's listed nouns beside a format, a data structure or a second request ("un gato en
ASCII", "un árbol binario", "un perro y sugiéreme nombres"), round 7's blind set, and
review 7's and round 8's draw-me lines the user asks about rather than asks for: translated
("Traduce al inglés: dibújame un gato"), checked ("¿Esta frase es correcta? Dibújame un
gato"), explained, quoted or attributed ("«Dibújame un cordero»: ¿quién lo dijo?").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.intent import composer_image_intent

_GROUPS: dict[str, list[str]] = json.loads(
    Path(__file__).with_name("language_misfires.json").read_text(encoding="utf-8")
)
MISFIRES = [
    pytest.param(text, id=f"group{n}-{i}")
    for n, texts in enumerate(_GROUPS.values())
    for i, text in enumerate(texts)
]


def test_every_review_is_here() -> None:
    reviews = {group.split(" (")[0] for group in _GROUPS}
    assert {f"review {n}" for n in range(1, 8)} <= reviews
    assert len(MISFIRES) >= 2150


@pytest.mark.parametrize("text", MISFIRES)
def test_no_picture(text: str) -> None:
    assert composer_image_intent(text, []).request is None
    assert not plan_turn(text).of_kind("image")
