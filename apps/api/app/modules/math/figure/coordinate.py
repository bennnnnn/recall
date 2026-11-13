"""Number lines, function graphs and plotted points, from what the question writes.

These parse with SymPy, so they run in the SymPy pool with the rest of a figure's build.
A function is drawn only as the question writes it: when the question holds a formula, the
read's must be that whole formula in the question's own letter (SymPy compares them; "x = 3"
is a vertical line, no function, and a question writing two functions has no one to draw);
a quantity described in words is drawn only as a line through every pair of values the
question states, two of them fixing it ("144 m at week 0 and 104 m after 10 weeks"); a rate
and one value ("falling 4 m each week") fix nothing the server can check. An inequality is
drawn only when it is the question's, the whole of it ("x > -3" is no part of "2x > -3"),
its whole numbers marked when only those are asked for.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from app.core.config import get_settings
from app.modules.math import solve as math_solve
from app.modules.math.figure.drawing import number_text
from app.modules.math.figure.grounding import number_value
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas import GraphBlockSpec, GraphSampleInput, NumberLineInterval
from app.modules.math.schemas.figure import NumberLineMark, PlotPoint, PointsGraphSpec
from app.services.solving import SolveServiceError

_MINUS = "\u2212"
_EN_DASH = "\u2013"
_DEFAULT_RANGE = 10.0
# A points plot shows at least -5..5 on each axis, and a unit past its farthest point.
_PLANE_REACH = 5.0
_COMPARATORS = {"≤": "<=", "≥": ">=", "=<": "<=", "=>": ">="}
# How near a stated value a line must pass, as a share of the value.
_ON_LINE = 1e-6
# Whole numbers marked one by one: more would crowd the line.
_MAX_MARKS = 25


def number_line(request: FigureRequest, texts: list[str]) -> dict[str, object] | None:
    if request.inequality.strip():
        return _inequality_line(request, texts)
    values: list[tuple[Fraction, str]] = []
    for written in request.numbers:
        value = number_value(written)
        if value is None:
            return None
        values.append((value, written.strip().replace("-", _MINUS)))
    return _marked(values)


def _marked(values: list[tuple[Fraction, str]]) -> dict[str, object] | None:
    """A number line with each value marked and labelled."""
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


def _inequality_line(request: FigureRequest, texts: list[str]) -> dict[str, object] | None:
    """The question's own inequality, the whole of it, shaded on the line; its whole-number
    solutions marked one by one when only those are asked for."""
    from app.modules.math.tool_check import same_inequalities, written_relations

    # Shown as the read copies it ("-2 < x ≤ 3"), compared in one spelling.
    inequality = request.inequality.replace(_MINUS, "-").replace(_EN_DASH, "-")
    plain = inequality
    for raw, spelled in _COMPARATORS.items():
        plain = plain.replace(raw, spelled)
    reference = next(
        (text for text in texts if any(op != "=" for _, op, _ in written_relations(text))), None
    )
    if reference is None or not same_inequalities(plain, reference):
        return None
    spec = math_solve.number_line_spec_from_expr(inequality)
    if spec is None:
        return None
    if not request.integers:
        return spec.model_dump()
    whole: list[tuple[Fraction, str]] = []
    for interval in spec.intervals:
        if interval.start is None or interval.end is None:
            return None  # endless: no picture marks every one
        low, high = math.ceil(interval.start), math.floor(interval.end)
        for n in range(low, high + 1):
            inside_low = n > interval.start or interval.start_inclusive
            inside_high = n < interval.end or interval.end_inclusive
            if inside_low and inside_high:
                whole.append((Fraction(n), str(n).replace("-", _MINUS)))
    return _marked(whole) if 0 < len(whole) <= _MAX_MARKS else None


def _dependent(lhs: Any, rhs: Any) -> Any | None:
    """The name a formula gives its value ("y", the f of "f(x)"), or None when the left side
    is no name: "y = 2x + 1" and "f(x) = x^2" name one, "2x + 1 = 7" none."""
    import sympy

    if isinstance(lhs, sympy.Symbol) and lhs not in rhs.free_symbols:
        return lhs
    if isinstance(lhs, sympy.Mul) and len(lhs.args) == 2 and rhs.free_symbols:
        name = [arg for arg in lhs.args if isinstance(arg, sympy.Symbol)]
        if len(name) == 2 and set(name) & rhs.free_symbols:
            return next(iter(set(name) - rhs.free_symbols), None)
    return None


def _written_formulas(text: str, variable: str) -> list[tuple[Any, Any]] | None:
    """The functions ``text`` writes to graph, each as (its formula, its variable): "y = 2x +
    1", "d = 144 - 4t", "y = 3", or a formula alone. "x = 3" is a vertical line, no function
    of x. None when the text writes no formula at all."""
    import sympy

    from app.modules.math.tool_check import written_expressions, written_relations

    relations = written_relations(text)
    expressions = written_expressions(text)
    if not relations and not expressions:
        return None
    formulas: list[tuple[Any, Any]] = []
    for lhs, op, rhs in relations:
        name = _dependent(lhs, rhs) if op == "=" else None
        symbols = rhs.free_symbols
        if name is None or len(symbols) > 1:
            continue
        own = next(iter(symbols)) if symbols else sympy.Symbol(variable)
        if not symbols and str(name) in {variable, "x"}:
            continue  # "x = 3": a vertical line
        formulas.append((rhs, own))
    formulas += [
        (expr, next(iter(expr.free_symbols))) for expr in expressions if len(expr.free_symbols) == 1
    ]
    return formulas if formulas or relations else None


def _drawn_formula(
    expr: str, variable: str, texts: list[str], pairs: list[tuple[float, float]]
) -> tuple[str, str] | None:
    """The function to draw and its variable: the formula the question writes, when the
    read's is that one whole formula (SymPy compares them, the read's letter put for the
    question's); or, when the question describes it in words, the read's own line only
    when the pairs of values the question states pin it (``_pinned``). A question writing
    two functions has no single one to draw."""
    import sympy

    from app.modules.math.tool_check import parse_formula, same_value

    parsed = parse_formula(expr)
    if parsed is None or not parsed.free_symbols <= {sympy.Symbol(variable)}:
        return None
    for text in texts:
        formulas = _written_formulas(text, variable)
        if formulas is None:
            continue
        distinct: list[tuple[Any, Any]] = []
        for formula, own in formulas:
            if not any(same_value(formula, seen) for seen, _ in distinct):
                distinct.append((formula, own))
        if len(distinct) != 1:
            return None
        formula, own = distinct[0]
        mine = parsed.subs(sympy.Symbol(variable), own)
        return (str(formula), str(own)) if same_value(mine, formula) else None
    return (expr, variable) if _pinned(parsed, sympy.Symbol(variable), pairs) else None


def _pinned(parsed: Any, symbol: Any, pairs: list[tuple[float, float]]) -> bool:
    """A line described in words, fixed by what the question states: it passes through
    every pair of values the question says together ("144 m at week 0", "104 m after 10
    weeks"), and two of them, at different places, fix it. A rate and one value ("144 m
    at week 0, falling 4 m a week") fix no line the server can check: "falls" read as a
    rise drew 144 + 4x (review, 2026-11-13), so nothing is drawn."""
    import sympy

    if not parsed.is_polynomial(symbol) or sympy.degree(parsed, symbol) > 1:
        return False
    if len({x for x, _ in pairs}) < 2:
        return False
    for x, y in pairs:
        value = parsed.subs(symbol, x)
        if not value.is_number or abs(float(value) - y) > _ON_LINE * max(1.0, abs(y)):
            return False
    return True


def function_graph(request: FigureRequest, texts: list[str]) -> dict[str, object] | None:
    expr = request.expr.strip().removeprefix("y=").removeprefix("y =").strip()
    pairs = [(pair.x, pair.y) for pair in request.pairs]
    variable = request.variable.strip() or "x"
    drawn = _drawn_formula(expr, variable, texts, pairs) if expr else None
    if drawn is None:
        return None
    expr, variable = drawn
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
