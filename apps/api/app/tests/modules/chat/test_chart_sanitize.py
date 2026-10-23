"""A ```chart the phone cannot draw becomes the table it holds, or goes."""

from __future__ import annotations

import json

import pytest

from app.modules.chat.chart_sanitize import chart_is_drawable, sanitize_chart_fences

# Live: "whats 72 fahrenheit in celsius" got this above the answer, and the phone
# showed "Could not render that chart".
_LIVE = (
    '```chart\ntype: scatter\ntitle: "Temperature Conversion"\ndata: |\n'
    "  Fahrenheit (°F) | Celsius (°C)\n  --------------- | ------------\n"
    "  32              | 0\n  72              | 22.2\n```\n\n"
    "$C = \\frac{5}{9}(72 - 32) \\approx 22.2^\\circ\\text{C}$."
)


@pytest.mark.parametrize(
    "spec",
    [
        # Vega-Lite, Vega, a layered chart, Chart.js and a series chart all draw.
        {"$schema": "vl", "mark": "bar", "data": {"values": [{"x": "a", "y": 1}]}},
        {"data": [{"name": "t", "values": [{"x": 1}]}], "marks": []},
        {"layer": [{"mark": "line", "data": {"values": [{"x": 1, "y": 2}]}}]},
        {"type": "bar", "data": {"labels": ["a"], "datasets": [{"data": [1]}]}},
        {"type": "line", "series": [{"name": "s", "points": [[0, 1]]}]},
    ],
)
def test_a_chart_with_its_data_inline_is_kept(spec: dict[str, object]) -> None:
    text = f"Here:\n\n```chart\n{json.dumps(spec)}\n```\n\nDone."
    assert chart_is_drawable(json.dumps(spec))
    assert sanitize_chart_fences(text) == text


def test_a_broken_chart_becomes_the_table_it_holds() -> None:
    assert sanitize_chart_fences(_LIVE) == (
        "| Fahrenheit (°F) | Celsius (°C) |\n|---|---|\n| 32 | 0 |\n| 72 | 22.2 |\n\n"
        "$C = \\frac{5}{9}(72 - 32) \\approx 22.2^\\circ\\text{C}$."
    )


@pytest.mark.parametrize(
    "body",
    [
        '{"mark": "line", "data": {"url": "data.csv"}}',
        '{"mark": "line", "data": {"sequence": {"start": 0, "stop": 10}}}',
        '{"mark": "line", "data": {"values": []}}',
        "type: bar\nvalues: 1, 2, 3",
        "",
    ],
)
def test_a_chart_with_nothing_to_draw_goes(body: str) -> None:
    assert (
        sanitize_chart_fences(f"Look:\n\n```chart\n{body}\n```\n\nThe end.") == "Look:\n\nThe end."
    )


def test_other_fences_are_left_alone() -> None:
    text = "```python\nprint('a | b')\n```\n\n```mermaid\ngraph TD; A-->B\n```\n"
    assert sanitize_chart_fences(text) == text
