"""A chart the model wrote, read as data the grounding can check.

Only the four shapes the server draws are read, each with one series: bars, a line or a pie
of one number per category, and a histogram of raw values. Anything else (a scatter, a box
plot, several series, a curve) is None: not this module's to judge, and left as it is.
"""

from __future__ import annotations

from typing import Any

from app.modules.charts.request import MAX_POINTS, MAX_VALUES, ChartKind, ChartPoint, ChartRequest

_MARKS: dict[str, ChartKind] = {"bar": "bar", "line": "line", "area": "line", "arc": "pie"}


def _mark(spec: dict[str, Any]) -> str:
    mark = spec.get("mark")
    if isinstance(mark, dict):
        mark = mark.get("type")
    return str(mark or "").lower()


def _fields(encoding: dict[str, Any]) -> tuple[list[str], list[str], str | None]:
    """The encoding's category fields, its number fields, and a binned field."""
    labels: list[str] = []
    numbers: list[str] = []
    binned: str | None = None
    for channel in encoding.values():
        if not isinstance(channel, dict) or not isinstance(channel.get("field"), str):
            continue
        field = channel["field"]
        if channel.get("bin"):
            binned = field
        elif channel.get("type") == "quantitative":
            numbers.append(field)
        elif channel.get("type") in {"nominal", "ordinal"}:
            labels.append(field)
    return labels, numbers, binned


def _text(value: float | int) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def model_chart_request(spec: Any) -> ChartRequest | None:
    """The model's chart as the data it draws, or None for a shape not read here."""
    if not isinstance(spec, dict) or "layer" in spec:
        return None
    kind = _MARKS.get(_mark(spec))
    data = spec.get("data")
    rows = data.get("values") if isinstance(data, dict) else None
    encoding = spec.get("encoding")
    if kind is None or not isinstance(rows, list) or not isinstance(encoding, dict):
        return None
    if not rows or not all(isinstance(row, dict) for row in rows):
        return None
    labels, numbers, binned = _fields(encoding)
    if binned is not None and kind == "bar" and not labels:
        values = [row.get(binned) for row in rows]
        if len(values) > MAX_VALUES or not all(_is_number(v) for v in values):
            return None
        return ChartRequest(kind="histogram", values=[_text(v) for v in values])
    if len(labels) != 1 or len(numbers) != 1 or len(rows) > MAX_POINTS:
        return None
    points: list[ChartPoint] = []
    for row in rows:
        label, value = row.get(labels[0]), row.get(numbers[0])
        if not isinstance(label, (str, int)) or not _is_number(value):
            return None
        points.append(ChartPoint(label=str(label), value=_text(value)))
    return ChartRequest(kind=kind, points=points)
