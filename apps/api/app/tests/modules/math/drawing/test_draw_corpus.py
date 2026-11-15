"""Descriptions a reply might write, valid and not, each drawn or left out as it should be.

The owner's rule (2026-11-14): the reply model says what a picture shows; the server checks
every item against the question and works out every coordinate; an item that fails is left
out, never drawn wrong. Each corpus entry is a question, the reply's working (its letters),
a ```draw description and what must come of it: drawn, with exactly these labels, or
nothing at all. Most entries that draw leave something out on purpose: a rate read as a
radius, an optimisation's answer as a label, a distance worked out, an unstated vector.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from app.modules.math.drawing.build import drawn_fence, first_drawn_fence
from app.modules.math.schemas.figure import FigureSpec

_CORPUS = json.loads(Path(__file__).with_name("draw_corpus.json").read_text())


def _body(fence: str) -> dict[str, Any]:
    assert fence.startswith("```geometry\n") and fence.endswith("\n```")
    body: dict[str, Any] = json.loads(fence.split("\n", 1)[1].rsplit("\n```", 1)[0])
    return body


def _labels(body: dict[str, Any]) -> list[str]:
    marks = [
        mark.get("label") or ("right" if mark.get("right") else "arc")
        for mark in body.get("angles", [])
    ]
    return [segment["label"] for segment in body["segments"] if segment.get("label")] + marks


@pytest.mark.parametrize("entry", _CORPUS, ids=[entry["id"] for entry in _CORPUS])
def test_draw_corpus_draws_or_leaves_out(entry: dict[str, Any]) -> None:
    fence = drawn_fence(entry["description"], [entry["question"]], entry["reply"])
    if entry["expect"] == "drop":
        assert fence is None
        return
    assert fence is not None
    body = _body(fence)
    FigureSpec.model_validate(body)
    labels = [label for label in _labels(body) if label not in {"right", "arc"}]
    expected = [label for label in entry["labels"] if label not in {"right", "arc"}]
    assert Counter(labels) == Counter(expected)
    marks = [label for label in _labels(body) if label in {"right", "arc"}]
    assert Counter(marks) == Counter(m for m in entry["labels"] if m in {"right", "arc"})
    if entry.get("shown") is not None:
        # The question's letters, each on its own point and on no other.
        named = {point["name"] for point in body["points"] if point.get("show")}
        assert named & set("ABCDPQ") == set(entry["shown"])


def test_draw_corpus_holds_both_outcomes_and_both_kinds() -> None:
    kinds = Counter(
        (
            json.loads(e["description"]).get("kind")
            if e["description"].startswith('{"')
            else "bad",
            e["expect"],
        )
        for e in _CORPUS
    )
    for kind in ("space", "shape"):
        assert kinds[(kind, "draw")] >= 10 and kinds[(kind, "drop")] >= 5


def test_the_first_description_that_holds_is_drawn() -> None:
    question = "Find the angle between the vectors (−1, 1, 1) and (2, 2, 2), and draw both."
    unstated = json.dumps(
        {"kind": "space", "items": [{"item": "vector", "name": "u", "to": [1, 1, 1]}]}
    )
    stated = json.dumps(
        {"kind": "space", "items": [{"item": "vector", "name": "u", "to": [-1, 1, 1]}]}
    )
    fence = first_drawn_fence([unstated, stated], [question], "Let $u$.")
    assert fence is not None and '"label":"u"' in fence
    assert first_drawn_fence([unstated], [question], "") is None
