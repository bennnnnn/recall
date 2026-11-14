"""A chart the model wrote, read as data the grounding can check.

``model_chart_kind`` says whether a chart is one of the four kinds the server draws: bars, a
line, a pie (Vega-Lite marks, or a Chart.js or series ``type``) or a histogram. Anything else
(a scatter, a box plot, a curve y = f(x)) is None: not this module's to judge, and left as
it is. ``model_chart_request`` reads one of the four as data, with one series: one number per
category, or a histogram's raw values. A chart of the four kinds it cannot read (several
series, a shape it does not know) is None too, and the caller takes it out: its numbers
cannot be checked (review, 2026-11-14).
"""

from __future__ import annotations

from typing import Any

from app.modules.charts.request import MAX_POINTS, MAX_VALUES, ChartKind, ChartPoint, ChartRequest

_MARKS: dict[str, ChartKind] = {
    "bar": "bar",
    "column": "bar",
    "line": "line",
    "area": "line",
    "arc": "pie",
    "pie": "pie",
    "donut": "pie",
    "doughnut": "pie",
    "histogram": "histogram",
}
# A Vega-Lite field a category is written in: a name, an order, a date or a month.
_LABEL_TYPES = frozenset({"nominal", "ordinal", "temporal"})


def _mark(spec: dict[str, Any]) -> str:
    mark = spec.get("mark")
    if isinstance(mark, dict):
        mark = mark.get("type")
    if mark is None and "layer" not in spec:
        mark = spec.get("type")  # a Chart.js config or a series chart names its kind here
    return str(mark or "").lower()


def model_chart_kind(spec: Any) -> ChartKind | None:
    """The kind of the model's chart when it is one the server draws, else None."""
    if not isinstance(spec, dict):
        return None
    if "layer" in spec:
        layers = spec["layer"] if isinstance(spec["layer"], list) else []
        marks = {_mark(layer) for layer in layers if isinstance(layer, dict)}
        return _MARKS.get(marks.pop()) if len(marks) == 1 else None
    return _MARKS.get(_mark(spec))


def _fields(encoding: dict[str, Any]) -> tuple[list[str], list[str], str | None, str | None]:
    """The encoding's category fields, its number fields, a binned field, and x's field."""
    labels: list[str] = []
    numbers: list[str] = []
    binned: str | None = None
    x_field: str | None = None
    for channel_name, channel in encoding.items():
        if not isinstance(channel, dict) or not isinstance(channel.get("field"), str):
            continue
        field = channel["field"]
        if channel_name == "x":
            x_field = field
        if channel.get("bin"):
            binned = field
        elif channel.get("type") == "quantitative":
            numbers.append(field)
        elif channel.get("type") in _LABEL_TYPES:
            labels.append(field)
    return labels, numbers, binned, x_field


def _text(value: float | int) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _points(labels: list[Any], values: list[Any], kind: ChartKind) -> ChartRequest | None:
    if not labels or len(labels) != len(values) or len(labels) > MAX_POINTS:
        return None
    if not all(isinstance(label, (str, int)) and not isinstance(label, bool) for label in labels):
        return None
    if not all(_is_number(value) for value in values):
        return None
    points = [
        ChartPoint(label=str(label), value=_text(value))
        for label, value in zip(labels, values, strict=True)
    ]
    return ChartRequest(kind=kind, points=points)


def _vega_request(spec: dict[str, Any], kind: ChartKind) -> ChartRequest | None:
    data = spec.get("data")
    rows = data.get("values") if isinstance(data, dict) else None
    encoding = spec.get("encoding")
    if not isinstance(rows, list) or not isinstance(encoding, dict) or not rows:
        return None
    if not all(isinstance(row, dict) for row in rows):
        return None
    labels, numbers, binned, x_field = _fields(encoding)
    if binned is not None and kind in {"bar", "histogram"} and not labels:
        values = [row.get(binned) for row in rows]
        if len(values) > MAX_VALUES or not all(_is_number(v) for v in values):
            return None
        return ChartRequest(kind="histogram", values=[_text(v) for v in values])
    if kind == "line" and not labels and len(numbers) == 2 and x_field in numbers:
        # A line over years written as numbers: x is the category.
        labels, numbers = [x_field], [field for field in numbers if field != x_field]
    if len(labels) != 1 or len(numbers) != 1:
        return None
    return _points(
        [row.get(labels[0]) for row in rows], [row.get(numbers[0]) for row in rows], kind
    )


def _series_request(spec: dict[str, Any], kind: ChartKind) -> ChartRequest | None:
    """A Chart.js config (``data.labels`` and ``data.datasets``) or a series chart
    (``labels`` and ``series`` or ``datasets``), with one series."""
    data = spec.get("data")
    block = data if isinstance(data, dict) else spec
    labels = block.get("labels")
    series = block.get("datasets", block.get("series"))
    if not isinstance(labels, list) or not isinstance(series, list) or len(series) != 1:
        return None
    one = series[0]
    values = one.get("data", one.get("values")) if isinstance(one, dict) else None
    return _points(labels, values, kind) if isinstance(values, list) else None


def model_chart_request(spec: Any) -> ChartRequest | None:
    """The model's chart as the data it draws, or None for a chart not read here: another
    kind (``model_chart_kind`` None), or one of the four in a shape with no single series."""
    kind = model_chart_kind(spec)
    if kind is None or not isinstance(spec, dict) or "layer" in spec:
        return None
    if "encoding" in spec:
        return _vega_request(spec, kind)
    return _series_request(spec, kind)
