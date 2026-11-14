"""A ```chart fence for checked data, in the shapes the phone draws.

The shapes are the chart contract's (``chat/prompt_constants/chart_shapes.json``), which the
phone's tests draw every one of: horizontal bars with the categories in the user's order, a
line through them in that order, a pie, and a histogram that bins the raw values itself.
"""

from __future__ import annotations

import json
from typing import Any

from app.modules.charts.request import ChartKind

_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"
# The phone's histogram shape: Vega-Lite bins the user's own values.
_MAX_BINS = 10


def _number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def _axis(field: str, kind: str, title: str | None, **extra: Any) -> dict[str, Any]:
    # An axis named by no word of the user's is untitled: never the field's own name.
    return {"field": field, "type": kind, "title": title, **extra}


def chart_fence(
    kind: ChartKind,
    *,
    pairs: list[tuple[str, float]] | None = None,
    values: list[float] | None = None,
    label_title: str | None = None,
    value_title: str | None = None,
) -> str | None:
    """The fence for a chart of checked data, or None for a kind it does not draw."""
    spec: dict[str, Any] = {"$schema": _SCHEMA}
    if kind == "histogram" and values:
        spec["data"] = {"values": [{"value": _number(v)} for v in values]}
        spec["mark"] = "bar"
        spec["encoding"] = {
            "x": {"field": "value", "bin": {"maxbins": _MAX_BINS}, "title": value_title},
            "y": {"aggregate": "count", "title": None},
        }
    elif kind in {"bar", "line", "pie"} and pairs:
        spec["data"] = {
            "values": [{"label": label, "value": _number(value)} for label, value in pairs]
        }
        if kind == "bar":
            spec["mark"] = "bar"
            spec["encoding"] = {
                "x": _axis("value", "quantitative", value_title),
                "y": _axis("label", "nominal", label_title, sort=None),
            }
        elif kind == "line":
            spec["mark"] = {"type": "line", "point": True}
            spec["encoding"] = {
                "x": _axis("label", "ordinal", label_title, sort=None),
                "y": _axis("value", "quantitative", value_title),
            }
        else:
            spec["mark"] = {"type": "arc"}
            spec["encoding"] = {
                "theta": _axis("value", "quantitative", value_title),
                "color": _axis("label", "nominal", label_title, sort=None),
            }
    else:
        return None
    return f"```chart\n{json.dumps(spec, separators=(',', ':'), ensure_ascii=False)}\n```"
