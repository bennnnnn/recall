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

from app.modules.math.drawing.build import drawn_fence, drawn_fences
from app.modules.math.drawing.question import read_question
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


def test_the_first_description_of_each_kind_that_holds_is_drawn() -> None:
    question = "Find the angle between the vectors (−1, 1, 1) and (2, 2, 2), and draw both."
    unstated = json.dumps(
        {"kind": "space", "items": [{"item": "vector", "name": "u", "to": [1, 1, 1]}]}
    )
    stated = json.dumps(
        {"kind": "space", "items": [{"item": "vector", "name": "u", "to": [-1, 1, 1]}]}
    )
    again = json.dumps(
        {"kind": "space", "items": [{"item": "vector", "name": "v", "to": [2, 2, 2]}]}
    )
    fences = drawn_fences([unstated, stated, again], [question], "Let $u$ and $v$.")
    # One figure: the first that holds; a second figure never joins it.
    assert len(fences) == 1 and '"label":"u"' in fences[0]
    assert drawn_fences([unstated], [question], "") == []


def _named_parts(entry: dict[str, Any]) -> bool:
    """A word problem's description that names a part by a letter the question or the reply
    uses ("r", "2r"), or by a number the reply gives a letter ("w = 3.36")."""
    if not entry["description"].startswith('{"'):
        return False
    description = json.loads(entry["description"])
    if description.get("kind") != "shape":
        return False
    question = read_question([entry["question"]], entry["reply"])
    values = [
        value.strip()
        for item in description.get("items", [])
        if isinstance(item, dict) and item.get("item") != "polygon"
        for key, value in item.items()
        if key not in {"item", "container", "open"} and isinstance(value, str)
    ]
    lettered = any(value[-1:] in question.letters for value in values if value[-1:].isalpha())
    given = {round(value, 2) for _letter, value, _places in question.reply_values}
    numbered = any(
        value.split()[0].replace(".", "", 1).isdigit()
        and round(float(value.split()[0]), 2) in given
        for value in values
        if value
    )
    return lettered or numbered


@pytest.mark.parametrize(
    "entry",
    [e for e in _CORPUS if e["expect"] == "draw" and _named_parts(e)],
    ids=lambda e: e["id"],
)
def test_a_word_problem_figure_keeps_a_label(entry: dict[str, Any]) -> None:
    """Round 2 (coordinator): a figure whose numbers the server cannot show keeps the
    letters they stand for, never no label at all (a window lost its r, h and w)."""
    fence = drawn_fence(entry["description"], [entry["question"]], entry["reply"])
    assert fence is not None
    assert [label for label in _labels(_body(fence)) if label not in {"right", "arc"}]
