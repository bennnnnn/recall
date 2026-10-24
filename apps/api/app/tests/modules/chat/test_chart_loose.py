"""A chart written as loose text is read into JSON the phone draws.

Qwen3.7 Flash answered "make that a bar chart" after a rainfall list (2026-10-24) with these
bodies, each a different made-up format around the same months and numbers; the phone
showed "Could not render that chart" for every one, and the server dropped it. The JSON
the server writes for each is in ``docs/fixtures/chart_bodies.json``, which the phone's
tests draw.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.chat.chart_bodies import chart_body_draws
from app.modules.chat.chart_loose import loose_chart_json

_FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "chart_bodies.json"
_DRAWN = {entry["name"]: entry["body"] for entry in json.loads(_FIXTURE.read_text())}

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MM = (15, 30, 60, 85, 80, 135, 280, 290, 190, 30, 6, 5)
_TITLE = "Monthly Rainfall in Addis Ababa (mm)"

_LIVE = {
    "a mermaid-like block with label: number lines": (
        f'bar\n  title "{_TITLE}"\n  x_axis "Month"\n  y_axis "Rainfall (mm)"\n  \n  data:\n'
        + "\n".join(f"    {month}: {mm}" for month, mm in zip(_MONTHS, _MM, strict=True))
    ),
    "JavaScript object literals after a header word": (
        f'bar\ntitle "{_TITLE}"\nyAxis "Rainfall (mm)"\ndata [\n'
        + ",\n".join(f'  {{label: "{m}", value: {mm}}}' for m, mm in zip(_MONTHS, _MM, strict=True))
        + "\n]"
    ),
    "YAML with an x-axis list and series": (
        f"type: bar\ntitle: {_TITLE}\nxAxis: [{', '.join(_MONTHS)}]\nyAxis:\n"
        "  label: Rainfall (mm)\n  min: 0\n  max: 350\n  step: 50\nseries:\n  - name: Rainfall\n"
        f"    data: [{', '.join(map(str, _MM))}]\n    color: #4A90E2"
    ),
    "YAML label/value rows": f"type: bar\ntitle: {_TITLE}\ndata:\n"
    + "\n".join(
        f"  - label: {month}\n    value: {mm}" for month, mm in zip(_MONTHS, _MM, strict=True)
    ),
    "mermaid xychart bars and a line": (
        'xychart-beta\n  title "Sales"\n  x-axis [Jan, Feb, Mar]\n  y-axis "Revenue" 0 --> 100\n'
        "  bar [10, 20, 30]\n  line [12, 18, 25]"
    ),
}


@pytest.mark.parametrize("name", list(_LIVE))
def test_a_loose_chart_becomes_json_the_phone_draws(name: str) -> None:
    read = loose_chart_json(_LIVE[name])
    assert read is not None
    assert chart_body_draws(read)
    # The phone's tests draw this exact body.
    assert read == _DRAWN[f"{name} (loose text, as the server writes it)"]


def test_the_months_numbers_and_titles_come_through() -> None:
    read = json.loads(
        loose_chart_json(_LIVE["a mermaid-like block with label: number lines"]) or ""
    )
    assert [row["label"] for row in read["data"]] == list(_MONTHS)
    assert [row["value"] for row in read["data"]] == list(_MM)
    assert (read["type"], read["title"], read["yLabel"]) == ("bar", _TITLE, "Rainfall (mm)")


@pytest.mark.parametrize(
    ("body", "labels"),
    [
        # YAML 1.1 reads these as a boolean, a date and a base-60 number: they are labels.
        ("type: bar\ndata:\n  No: 3\n  Yes: 5", ["No", "Yes"]),
        ("bar\ndata:\n  2024-01: 5\n  2024-02: 7", ["2024-01", "2024-02"]),
        ("type: bar\nlabels: [1:30, 2:00]\ndata: [4, 6]", None),
    ],
)
def test_labels_stay_the_words_written(body: str, labels: list[str] | None) -> None:
    read = json.loads(loose_chart_json(body) or "")
    if labels is None:
        assert read["labels"] == ["1:30", "2:00"]
    else:
        assert [row["label"] for row in read["data"]] == labels


@pytest.mark.parametrize(
    "body",
    [
        # JSON is the JSON checks' to judge, drawable or not.
        '{"type": "bar", "data": {"labels": ["a"], "datasets": [{"data": [1]}]}}',
        '{"mark": "line", "data": {"url": "data.csv"}}',
        # Nothing to draw: words, a table as text, a series with no numbers.
        "just some words about rainfall",
        "type: scatter\ndata: |\n  F | C\n  32 | 0\n  72 | 22.2",
        "type: bar\ndata:\n  - label: Jan\n    value: lots",
        "",
        # Aliases repeat a node by reference: written out, they grew without bound.
        "a: &x [1, 2, 3]\nb: [*x, *x, *x]\nc: [*b, *b, *b]",
        "bar\ndata:\n  Jan: 1\n" + "  x: [" * 2000,
    ],
)
def test_what_holds_no_chart_is_not_one(body: str) -> None:
    assert loose_chart_json(body) is None
