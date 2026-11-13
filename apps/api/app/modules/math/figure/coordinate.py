"""Number lines, function graphs and plotted points, from what the question writes.

These parse with SymPy, so they run in the SymPy pool with the rest of a figure's build.
A function is drawn only as the question writes it: when the question holds a formula, the
read's must be the same one (SymPy compares them); a quantity described in words ("144 m
at week 0, falling 4 m each week") is drawn from the stated numbers alone. An inequality is
drawn only when the question writes it as read.
"""

from __future__ import annotations

import json
import re
from fractions import Fraction

from app.core.config import get_settings
from app.modules.math import solve as math_solve
from app.modules.math.figure.drawing import number_text
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas import GraphBlockSpec, GraphSampleInput, NumberLineInterval
from app.modules.math.schemas.figure import NumberLineMark, PlotPoint, PointsGraphSpec
from app.services.solving import SolveServiceError

_MINUS = "\u2212"
_EN_DASH = "\u2013"
_DEFAULT_RANGE = 10.0
# A points plot shows at least -5..5 on each axis, and a unit past its farthest point.
_PLANE_REACH = 5.0
_NUMBER = re.compile(r"^\s*([+-]?)\s*(\d+(?:\.\d+)?)(?:\s+(\d+)\s*/\s*(\d+)|\s*/\s*(\d+))?\s*$")
_COMPARATORS = {"≤": "<=", "≥": ">=", "=<": "<=", "=>": ">="}


def _plain(text: str) -> str:
    """Text as compared: one minus sign, one spelling of each comparator, no spaces."""
    for old, new in (*_COMPARATORS.items(), (_MINUS, "-"), (_EN_DASH, "-")):
        text = text.replace(old, new)
    return re.sub(r"\s+", "", text)


def number_value(written: str) -> Fraction | None:
    """'-5/2', '1.5', '2 1/2' as an exact value; None for anything else."""
    match = _NUMBER.match(written.replace(_MINUS, "-").replace(_EN_DASH, "-"))
    if match is None:
        return None
    sign, whole, top, bottom, denominator = match.groups()
    value = Fraction(whole)
    if top is not None and bottom is not None and int(bottom):
        value += Fraction(int(top), int(bottom))
    elif denominator is not None:
        if not int(denominator):
            return None
        value = Fraction(whole) / int(denominator)
    return -value if sign == "-" else value


def number_line(request: FigureRequest, texts: list[str]) -> dict[str, object] | None:
    if request.inequality.strip():
        return _inequality_line(request.inequality, texts)
    values: list[tuple[Fraction, str]] = []
    for written in request.numbers:
        value = number_value(written)
        if value is None:
            return None
        values.append((value, written.strip().replace("-", _MINUS)))
    if not values:
        return None
    values.sort(key=lambda item: item[0])
    intervals = [
        NumberLineInterval(start=float(v), end=float(v), start_inclusive=True, end_inclusive=True)
        for v, _ in values
    ]
    title = ", ".join(label for _, label in values)
    spec = GraphBlockSpec(type="number_line", expr=title, title=title[:64], intervals=intervals)
    marks = [NumberLineMark(x=float(v), label=label).model_dump() for v, label in values]
    return {**spec.model_dump(), "marks": marks}


def _inequality_line(inequality: str, texts: list[str]) -> dict[str, object] | None:
    """The question's own inequality: one it writes, as written, shaded on the line."""
    if not any(_plain(inequality) in _plain(text) for text in texts):
        return None
    spec = math_solve.number_line_spec_from_expr(inequality.replace(_MINUS, "-"))
    return None if spec is None else spec.model_dump()


def _same_formula(expr: str, variable: str, texts: list[str]) -> bool:
    """The read's function is the question's: the formula the question writes in its
    variable, or, when it writes none, a quantity described in words (whose numbers the
    grounding checked)."""
    from app.modules.math.tool_check import matched_user_text, writes_formula_in

    written = [text for text in texts if writes_formula_in(text, variable)]
    if not written:
        return True
    call = {"action": "graph", "expr": expr}
    return matched_user_text(json.dumps(call), written) is not None


def function_graph(request: FigureRequest, texts: list[str]) -> dict[str, object] | None:
    expr = request.expr.strip().removeprefix("y=").removeprefix("y =").strip()
    variable = request.variable.strip() or "x"
    if not expr or not _same_formula(expr, variable, texts):
        return None
    explicit = request.x_min is not None and request.x_max is not None
    x_min = request.x_min if request.x_min is not None else -_DEFAULT_RANGE
    x_max = request.x_max if request.x_max is not None else _DEFAULT_RANGE
    if x_max <= x_min:
        return None
    settings = get_settings()
    try:
        sample = math_solve.sample_function(
            GraphSampleInput(
                expr=expr[: settings.math_max_expr_length],
                variable=variable,
                x_min=x_min,
                x_max=x_max,
                n=settings.math_graph_max_points,
            )
        )
    except (SolveServiceError, ValueError):
        return None
    if len(sample.points) < 2:
        return None
    spec = GraphBlockSpec(
        expr=sample.expr,
        variable=sample.variable,
        x_min=sample.x_min,
        x_max=sample.x_max,
        domain_explicit=explicit,
        points=sample.points,
        segments=sample.segments if len(sample.segments) > 1 else [],
        holes=sample.holes,
        x_label=request.x_label.strip() or None,
        y_label=request.y_label.strip() or None,
    )
    return spec.model_dump()


def _coordinate(value: float) -> str:
    return number_text(value).replace("-", _MINUS)


def points_graph(request: FigureRequest) -> dict[str, object] | None:
    if not request.points:
        return None
    marks = [
        PlotPoint(
            x=point.x,
            y=point.y,
            label=f"{point.name.strip()}({_coordinate(point.x)}, {_coordinate(point.y)})",
        )
        for point in request.points
    ]
    xs = [point.x for point in marks]
    ys = [point.y for point in marks]
    reach_x = max(_PLANE_REACH, max(abs(x) for x in xs) + 1)
    reach_y = max(_PLANE_REACH, max(abs(y) for y in ys) + 1)
    spec = PointsGraphSpec(
        title=", ".join(point.label for point in marks)[:64],
        points=marks,
        x_min=-reach_x,
        x_max=reach_x,
        y_min=-reach_y,
        y_max=reach_y,
        quadrants=request.quadrants,
    )
    return spec.model_dump()
