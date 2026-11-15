"""Graph descriptions a reply might write, valid and not, each drawn or left out as it should be.

The owner's rule (2026-11-14): the reply model says what a picture shows; the server checks
every item against the question and works out every coordinate; an item that fails is left
out, never drawn wrong. Each entry is a question, a ```draw description of kind "plot", and
what must come of it: nothing, or a ```graph ``plot`` with exactly these curves, lines,
labelled points, open circles and regions. The round-3 targets (``r3_``) and Unit 5's
integral pictures (``u_``) draw; the rest are look-alikes and slips each check catches: a
formula the question never writes, a piece under its neighbour's condition, a letter's
value where the pieces do not meet, a tangent at a y-value, rectangles the question does
not ask for, an axis it does not turn about.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from app.modules.math.drawing.build import drawn_fence, drawn_fences
from app.modules.math.schemas.plot import PlotGraphSpec

_CORPUS = json.loads(Path(__file__).with_name("plot_corpus.json").read_text())


def _graph(fence: str) -> PlotGraphSpec:
    assert fence.startswith("```graph\n") and fence.endswith("\n```")
    return PlotGraphSpec.model_validate_json(fence.split("\n", 1)[1].rsplit("\n```", 1)[0])


@pytest.mark.parametrize("entry", _CORPUS, ids=[entry["id"] for entry in _CORPUS])
def test_plot_corpus_draws_or_leaves_out(entry: dict[str, Any]) -> None:
    fence = drawn_fence(entry["description"], [entry["question"]], "")
    if entry["expect"] == "drop":
        assert fence is None
        return
    assert fence is not None
    graph = _graph(fence)
    assert [curve.label for curve in graph.curves] == entry["curves"]
    assert sorted(f"{line.role}:{line.label}" for line in graph.lines) == entry["lines"]
    assert Counter(p.label for p in graph.points if p.label) == Counter(entry["points"])
    assert sum(p.open for p in graph.points) == entry["open"]
    assert sorted(region.kind for region in graph.regions) == entry["regions"]
    # Every point the graph marks is in its window: none is cut off.
    for point in graph.points:
        assert graph.x_min <= point.x <= graph.x_max and graph.y_min <= point.y <= graph.y_max


def test_plot_corpus_holds_both_outcomes() -> None:
    outcomes = Counter(entry["expect"] for entry in _CORPUS)
    assert outcomes["draw"] >= 40 and outcomes["drop"] >= 6


def test_a_figure_and_a_graph_are_both_drawn() -> None:
    question = (
        "Find the area enclosed by y = 4 − x² and y = 3x, shade it, and draw a cone of "
        "radius 3 cm and height 4 cm."
    )
    plot = json.dumps({"kind": "plot", "items": [{"item": "curve", "name": "f", "y": "4 - x^2"}]})
    cone = json.dumps(
        {"kind": "shape", "items": [{"item": "cone", "radius": "3 cm", "height": "4 cm"}]}
    )
    fences = drawn_fences([plot, cone, plot], [question], "")
    assert sorted(fence.split("\n", 1)[0] for fence in fences) == ["```geometry", "```graph"]
