"""Charts of the user's own numbers: which turns the server draws, and what it draws.

``chart_corpus.json`` holds messages with a reading a model might give (the chart read's
JSON) and, where a turn has one, a reply with the model's own chart. Each entry says what
the reply must end up with: the server's chart of exactly those labels and values, or no
chart of the four kinds at all. Look-alikes (a curve, a chart of searched facts, code, a
scatter plot, "the plot of a film") must never be a chart turn. A wrong picture is never
acceptable (owner decision, 2026-11-13): a reading that adds, drops, changes or mis-pairs a
number draws nothing. When a rule that reads the user's words widens, its look-alikes go here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.modules.charts.read import chart_for_reading
from app.modules.charts.request import ChartRequest
from app.modules.chat.chart_bodies import chart_body_draws, parse_chart_body
from app.modules.chat.chart_turn import chart_turn, placed_charts
from app.services.md_fence_scan import iter_closed_fences

_ENTRIES: list[dict[str, Any]] = json.loads(
    Path(__file__).with_name("chart_corpus.json").read_text(encoding="utf-8")
)["entries"]
_KINDS = {"bar": "bar", "line": "line", "arc": "pie"}


def _chart_of(spec: dict[str, Any]) -> dict[str, Any]:
    """What a server-built chart shows: its kind, labels and values."""
    rows = spec["data"]["values"]
    mark = spec["mark"]["type"] if isinstance(spec["mark"], dict) else spec["mark"]
    if "bin" in spec["encoding"].get("x", {}):
        return {"kind": "histogram", "values": [row["value"] for row in rows]}
    return {
        "kind": _KINDS[mark],
        "labels": [row["label"] for row in rows],
        "values": [row["value"] for row in rows],
    }


def _outcome(entry: dict[str, Any]) -> dict[str, Any] | None:
    earlier = [tuple(pair) for pair in entry["earlier"]]
    turn = chart_turn(entry["prompt"], earlier)
    if turn is None:
        return None
    data, named = turn
    reading = ChartRequest.model_validate(entry["reading"]) if entry["reading"] else None
    drawn = chart_for_reading(reading, data, named)
    text = placed_charts(entry["reply"], drawn, data) if entry["reply"] else (drawn or "")
    charts = [body for _start, _end, body in iter_closed_fences(text, "chart")]
    assert len(charts) <= 1, text
    if not charts:
        return None
    assert chart_body_draws(charts[0]), charts[0]
    return _chart_of(parse_chart_body(charts[0]))


@pytest.mark.parametrize("entry", _ENTRIES, ids=[entry["id"] for entry in _ENTRIES])
def test_chart_corpus(entry: dict[str, Any]) -> None:
    if entry["id"].startswith("lookalike-"):
        assert chart_turn(entry["prompt"], [tuple(p) for p in entry["earlier"]]) is None
        return
    if entry["expect"] == {"kept": True}:
        turn = chart_turn(entry["prompt"], [tuple(p) for p in entry["earlier"]])
        assert turn is not None
        assert placed_charts(entry["reply"], None, turn[0]) == entry["reply"], entry["note"]
        return
    assert _outcome(entry) == entry["expect"], entry["note"] or entry["prompt"]


def test_the_corpus_holds_charts_refusals_and_look_alikes() -> None:
    drawn = [e for e in _ENTRIES if e["expect"] is not None and "kind" in e["expect"]]
    refused = [e for e in _ENTRIES if e["expect"] is None and not e["id"].startswith("lookalike-")]
    lookalikes = [e for e in _ENTRIES if e["id"].startswith("lookalike-")]
    assert {e["expect"]["kind"] for e in drawn} == {"bar", "pie", "line", "histogram"}
    assert len(refused) >= 8 and len(lookalikes) >= 15
