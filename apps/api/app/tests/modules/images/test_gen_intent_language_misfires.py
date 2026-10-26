"""Every misfire the four reviews found, and the round-5 probes: answered in words.

A misfire (a picture drawn where the user wanted words) costs a daily picture and the
answer. ``language_misfires.json`` holds each sentence a review named as drawn wrongly
(physics homework, plans, tables, algorithms, idioms, "Dibuja un ejemplo", "Mal den
Teufel nicht an die Wand", a Docker image…), the reviewers' non-picture probe lines,
and the everyday lines with picture words written for round 5, most of them in a
draw-me shape ("Dibújame la pirámide alimenticia", "Zeichne mir einen Trainingsplan").
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
    assert {"review 1", "review 2", "review 3", "review 4"} <= reviews
    assert len(MISFIRES) >= 850


@pytest.mark.parametrize("text", MISFIRES)
def test_no_picture(text: str) -> None:
    assert composer_image_intent(text, []).request is None
    assert not plan_turn(text).of_kind("image")
