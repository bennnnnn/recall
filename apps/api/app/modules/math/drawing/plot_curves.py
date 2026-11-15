"""A graph's curves and lines, each the question's own, and the names its axes carry.

A curve's formula is one the question writes, compared with SymPy, in the question's own
letter ("v(t) = 3t² - 12t" draws against t and v), or an antiderivative of one, which SymPy
confirms by differentiating it back: a family F(x) + C is drawn once for each constant, each
labelled with its C. A line is one the question writes ("the line y = 3", "x = -3"). A
function in pieces is held clause by clause (``plot_pieces``). An axis's name is the
question's letter, its unit one the question writes.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Literal

from sympy import Expr, Integral, Rational, Symbol, integrate

from app.modules.math.drawing.plot_check import reach, stated
from app.modules.math.drawing.plot_items import AxisNames, Curve, Line
from app.modules.math.drawing.plot_labels import (
    equation_text,
    formula_text,
    line_text,
    number_text,
)
from app.modules.math.drawing.plot_pieces import formula, formula_shape, pieces_shape, value
from app.modules.math.drawing.plot_question import PlotQuestion, plain
from app.modules.math.drawing.plot_scene import DrawnCurve, DrawnLine, Scene
from app.modules.math.drawing.real_curve import RealFunction, as_real
from app.modules.math.tool_check import parse_formula, same_value

_X, _Y = Symbol("x"), Symbol("y")
_MOST_CURVES = 5
_MOST_LINES = 4
_LABEL_CHARS = 48
# Constants of a family the question leaves to the reply: a few small whole numbers.
_FAMILY_REACH = 5
# Where an antiderivative is compared with SymPy's: a few places most functions are defined.
_SAMPLES = (0.37, 1.3, 2.9, 4.7)
# Names that call a function by name, not a quantity an axis measures.
_FUNCTION_NAMES = frozenset({"f", "g", "h", "F", "G", "y", ""})


def _written_sideways(expr: Any, question: PlotQuestion) -> bool:
    return any(
        w.name == "x" and w.expr.free_symbols <= {_Y} and same_value(w.expr, expr)
        for w in question.formulas
    )


def _own_formula(text: str, question: PlotQuestion) -> tuple[Any, str, str, bool] | None:
    """The formula in x, the question's letter for x, its name for y, and whether it is an
    antiderivative of the question's function rather than the function itself."""
    parsed = parse_formula(plain(text))
    if not isinstance(parsed, Expr) or len(parsed.free_symbols) > 1:
        return None
    letter = next(iter(parsed.free_symbols), _X)
    for written in question.formulas:
        if written.name == "x" or not written.expr.free_symbols <= {letter}:
            continue
        # "v(t)" names what an axis measures; "k(x)" only names a function.
        quantity = letter != _X and written.name not in _FUNCTION_NAMES
        name = written.name if quantity else "y"
        if same_value(written.expr, parsed):
            return parsed.subs(letter, _X), str(letter), name, False
        if written.expr.free_symbols and _derivative_is(parsed, written.expr, letter):
            if _no_constant(parsed, written.expr, letter):
                return parsed.subs(letter, _X), str(letter), "y", True
    return None


def _derivative_is(antiderivative: Any, integrand: Any, letter: Symbol) -> bool:
    """SymPy's derivative of ``antiderivative`` is ``integrand`` on the real line (the
    derivative of ln|x| is 1/x), compared where both have values."""
    slope = RealFunction(as_real(antiderivative, letter))
    target = RealFunction(as_real(integrand, letter))
    pairs = [(slope.at(x, 1), target.at(x)) for x in (*_SAMPLES, *(-v for v in _SAMPLES))]
    found = [(a, b) for a, b in pairs if math.isfinite(a) and math.isfinite(b)]
    return len(found) >= 2 and all(abs(a - b) < 1e-9 * (1 + abs(b)) for a, b in found)


def _no_constant(antiderivative: Any, integrand: Any, letter: Symbol) -> bool:
    """``antiderivative`` is SymPy's own, with no constant added: a constant the reply chose
    (an initial value, a C) is no value the server can check. ln|x| is ln x where both are
    defined; a family's constants are its ``shifts``, labelled."""
    try:
        own = integrate(integrand, letter)
    except (ValueError, TypeError, NotImplementedError):
        return False
    if own.has(Integral):
        return False
    gap = RealFunction(as_real(antiderivative - own, letter))
    values = [gap.at(x) for x in _SAMPLES]
    found = [v for v in values if math.isfinite(v)]
    return bool(found) and all(abs(v) < 1e-9 for v in found)


def _domain(
    curve: Curve, question: PlotQuestion, split: bool
) -> tuple[Any, Any] | Literal[False] | None:
    """The stated interval the curve is drawn on; None for none, and for one the question
    does not state, a window the reply chose (the curve is drawn where the picture shows it).
    False when that interval is a piece: the reply wrote one function as curves of one name
    (c011's x² + 1 "on [-10, -7]", 15 - 5x "on [-7, 4]"), and a whole parabola would stand
    for f."""
    if curve.domain is None:
        return None
    ends = [value(text) for text in curve.domain]
    held = [stated(end, question) if end is not None else None for end in ends]
    if held[0] is not None and held[1] is not None and float(held[0]) < float(held[1]):
        return held[0], held[1]
    return False if split else None


def _shift(text: str, question: PlotQuestion) -> Any | None:
    """A family's constant: one the question writes, or a small whole number."""
    number = value(text)
    if number is None:
        return None
    if any(abs(float(v) - float(number)) < 1e-12 for v in question.values):
        return number
    return number if number.is_Integer and abs(number) <= _FAMILY_REACH else None


def _curves(
    curve: Curve, question: PlotQuestion, color: int, scene: Scene, split: bool
) -> list[DrawnCurve]:
    search = (-reach(question), reach(question))
    name = curve.name or f"curve{color}"
    if curve.x and not curve.y and not curve.pieces:
        expr = formula(curve.x, _Y)
        if expr is None or not _written_sideways(expr, question):
            return []
        label = equation_text("x", expr.subs(_Y, Symbol("y")))
        return [
            DrawnCurve(name, label, color, sideways=RealFunction(as_real(expr, _Y)), search=search)
        ]
    if curve.pieces:
        shape = pieces_shape(curve, question)
        return [] if shape is None else [DrawnCurve(name, "", color, shape, search=search)]
    found = _own_formula(curve.y, question)
    domain = _domain(curve, question, split)
    if found is None or domain is False:
        return []
    expr, letter, quantity, antiderivative = found
    if isinstance(domain, tuple):
        search = (float(domain[0]), float(domain[1]))
    scene.x_label = letter
    scene.y_label = quantity
    label = f"{quantity} = {formula_text(expr.subs(_X, Symbol(letter)))}"
    if antiderivative and curve.shifts:
        constants = [c for text in curve.shifts if (c := _shift(text, question)) is not None]
        return [
            DrawnCurve(
                name if i == 0 else f"{name}~{i}",
                f"C = {number_text(c)}",
                color + i,
                formula_shape(expr + c, domain),
                search=search,
                stated_domain=domain is not None,
            )
            for i, c in enumerate(constants[:_MOST_CURVES])
        ]
    shown = label if len(label) <= _LABEL_CHARS else ""
    shape = formula_shape(expr, domain)
    return [DrawnCurve(name, shown, color, shape, search=search, stated_domain=domain is not None)]


def _through(line: Line, question: PlotQuestion, color: int) -> DrawnLine | None:
    """The line through two points the question writes, "the line through (-4, -1) and
    (5, 4)": its slope and offset worked out exactly."""
    ends: list[tuple[Any, Any]] = [
        (a, b)
        for a, b in ((value(p), value(q)) for p, q in line.through)
        if a is not None and b is not None
    ]
    if len(ends) != 2:
        return None
    written = {
        (Rational(p.numerator, p.denominator), Rational(q.numerator, q.denominator))
        for p, q in question.pairs
    }
    (x0, y0), (x1, y1) = ends
    if {(x0, y0), (x1, y1)} - written or (x0, y0) == (x1, y1):
        return None
    if x0 == x1:
        return DrawnLine(vertical=x0, label=equation_text("x", x0), color=color)
    slope = (y1 - y0) / (x1 - x0)
    offset = y0 - slope * x0
    return DrawnLine(slope, offset, label=line_text(slope, offset), color=color)


def _line(line: Line, question: PlotQuestion, color: int) -> DrawnLine | None:
    if line.through:
        return _through(line, question, color)
    if line.x and not line.y:
        at = value(line.x)
        # The question's own value, as it writes it (-1/2, never the reply's -0.5).
        own = [
            w.expr
            for w in question.formulas
            if at is not None and w.name == "x" and w.expr.is_number and same_value(w.expr, at)
        ]
        if not own:
            return None
        return DrawnLine(vertical=own[0], label=equation_text("x", own[0]), color=color)
    expr = formula(line.y)
    slope = expr.diff(_X) if expr is not None else None
    if expr is None or slope is None or slope.free_symbols:
        return None
    written = any(w.name != "x" and same_value(w.expr, expr) for w in question.formulas)
    if not written and not _through_two(expr, question):
        return None
    return DrawnLine(slope, expr.subs(_X, 0), label=equation_text("y", expr), color=color)


def _through_two(expr: Any, question: PlotQuestion) -> bool:
    """A line the reply worked out through two points the question writes ("the line
    through (-4, -1) and (5, 4)" written y = 5x/9 + 11/9): every such point checked on it."""
    on = [
        (p, q)
        for p, q in question.pairs
        if expr.subs(_X, Rational(p.numerator, p.denominator))
        == Rational(q.numerator, q.denominator)
    ]
    return len({p for p, _q in on}) >= 2


def _axis_name(text: str, letter: str, question: PlotQuestion) -> str | None:
    """ "t (s)": the axis's own letter, and a unit the question writes."""
    head, _, unit = text.partition("(")
    unit = unit.rstrip(")").strip()
    if head.strip() != letter:
        return None
    if unit and unit.lower() not in question.words:
        return None
    return text.strip()


def add_curves(items: list[Any], question: PlotQuestion, scene: Scene) -> None:
    color = 0
    names = Counter(item.name for item in items if isinstance(item, Curve) and item.name)
    for item in items:
        if isinstance(item, Curve) and len(scene.curves) < _MOST_CURVES:
            for drawn in _curves(item, question, color, scene, names[item.name] > 1):
                if drawn.name not in scene.curves and len(scene.curves) < _MOST_CURVES:
                    scene.curves[drawn.name] = drawn
                    color += 1
    for item in items:
        if isinstance(item, Line) and len(scene.lines) < _MOST_LINES:
            line = _line(item, question, color)
            if line is not None:
                scene.lines[item.name or f"line{color}"] = line
                color += 1
    for item in items:
        if isinstance(item, AxisNames):
            scene.x_label = _axis_name(item.x, scene.x_label, question) or scene.x_label
            scene.y_label = _axis_name(item.y, scene.y_label, question) or scene.y_label
