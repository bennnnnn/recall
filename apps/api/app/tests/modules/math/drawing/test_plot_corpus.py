"""Graph descriptions a reply might write, valid and not, each drawn or left out as it should be.

The owner's rule (2026-11-14): the reply model says what a picture shows; the server checks
every item against the question and works out every coordinate; an item that fails is left
out, never drawn wrong. Each entry is a question, a ```draw description of kind "plot", and
what must come of it: nothing, or a ```graph ``plot`` with exactly these curves, lines,
points, open circles and regions. With no reply's working to agree with them, the points
and lines the server worked out carry no labels; a point the question writes does. The round-3 targets (``r3_``) and Unit 5's
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
    drawn = sorted([round(p.x, 2), round(p.y, 2), p.label] for p in graph.points)
    assert drawn == entry["points"]
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


_C018 = (
    "Find the equation of the line tangent to the graph of y = x² − 5x + 1 at the point(s) "
    "where the curve crosses the line y = 7. Draw the curve, the line y = 7 and the tangent "
    "line(s)."
)
_C018_PLOT = json.dumps(
    {
        "kind": "plot",
        "items": [
            {"item": "curve", "name": "f", "y": "x^2 - 5x + 1"},
            {"item": "line", "name": "L", "y": "7"},
            {"item": "tangent", "to": "f", "at": "-1"},
            {"item": "tangent", "to": "f", "at": "6"},
        ],
    }
)


@pytest.mark.parametrize(
    ("reply", "points", "lines"),
    [
        # The working writes the points and both tangents: every label shows.
        ("$x = -1$ or $x = 6$, so $(-1, 7)$ and $(6, 7)$. Tangents: $y = -7x$ and "
         "$y = 7x - 35$.", ["(6, 7)", "(\u22121, 7)"], ["y = 7", "y = 7x \u2212 35", "y = \u22127x"]),
        # A slip in the working (y = 7x - 36): that tangent is drawn, its label left off.
        ("$(-1, 7)$ and $(6, 7)$. Tangents: $y = -7x$ and $y = 7x - 36$.",
         ["(6, 7)", "(\u22121, 7)"], ["y = 7", "y = \u22127x"]),
        # No working: the server's values are drawn, none of them named.
        ("", [], ["y = 7"]),
    ],
)  # fmt: skip
def test_a_worked_out_label_shows_only_when_the_reply_agrees(
    reply: str, points: list[str], lines: list[str]
) -> None:
    fence = drawn_fence(_C018_PLOT, [_C018], reply)
    assert fence is not None
    graph = _graph(fence)
    assert len(graph.lines) == 3 and len(graph.points) == 2
    assert sorted(p.label for p in graph.points if p.label) == sorted(points)
    assert sorted(line.label for line in graph.lines if line.label) == sorted(lines)
