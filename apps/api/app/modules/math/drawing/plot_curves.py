"""A graph's curves and lines, each the question's own, and the names its axes carry.

A curve's formula is one the question writes, compared with SymPy, in the question's own
letter ("v(t) = 3t² - 12t" draws against t and v), or, when the question asks for
antiderivatives, one of those, which SymPy confirms by differentiating it back: a family
F(x) + C is drawn once for each constant, each labelled with its C. A line is one the
question writes ("the line y = 3", "x = -3"); a number is a level line only when the
question names y or a function equal to it, never "a = 3". A
function in pieces is held clause by clause (``plot_pieces``). An axis's name is the
question's letter, its unit one the question writes.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from sympy import Expr, Rational, Symbol

from app.modules.math.drawing.plot_check import reach, stated_interval
from app.modules.math.drawing.plot_items import AxisNames, Curve, Line
from app.modules.math.drawing.plot_labels import (
    equation_text,
    formula_text,
    line_text,
    number_text,
)
from app.modules.math.drawing.plot_pieces import formula, formula_shape, pieces_shape
from app.modules.math.drawing.plot_question import PlotQuestion, Written
from app.modules.math.drawing.plot_reading import Condition, number, plain, same_number
from app.modules.math.drawing.plot_scene import DrawnCurve, DrawnLine, Scene
from app.modules.math.drawing.real_curve import RealFunction, as_real
from app.modules.math.solve.antiderivative import antiderivative_forms
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


@dataclass(frozen=True)
class _Own:
    """A curve's formula in x, the question's letter for x and its name for y, whether it
    is an antiderivative of the question's function, and the question's own formula."""

    expr: Any
    letter: str
    name: str
    antiderivative: bool
    written: Written | None


def _own_formula(text: str, question: PlotQuestion) -> _Own | None:
    """The question's own formula the reply's ``text`` is, as the question writes it: its
    holes and its domain kept ((x² - 1)/(x - 1) described as x + 1 keeps its hole at 1), or
    an antiderivative of it when antiderivatives are asked."""
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
        if not parsed.free_symbols and not _a_level_line(written, question):
            continue  # "a = 3", "where y = 4" name values, never the line y = 3
        if same_value(written.expr, parsed):
            return _Own(written.expr.subs(letter, _X), str(letter), name, False, written)
        if not question.antiderivatives:
            continue  # x² is no picture of f(x) = 2x unless antiderivatives are asked for
        if written.expr.free_symbols and _derivative_is(parsed, written.expr, letter):
            if _no_constant(parsed, written.expr, letter):
                return _Own(parsed.subs(letter, _X), str(letter), "y", True, None)
    return None


def _a_level_line(written: Written, question: PlotQuestion) -> bool:
    """A number the question writes is the line y = c when it names y (or a function of the
    variable) equal to it and says it of no point ("find the gradient where y = 4")."""
    if not written.defines:
        return False
    return not any(same_number(point, written.expr) for point in question.y_points)


def _derivative_is(antiderivative: Any, integrand: Any, letter: Symbol) -> bool:
    """SymPy's derivative of ``antiderivative`` is ``integrand`` on the real line (the
    derivative of ln|x| is 1/x), compared where both have values."""
    slope = RealFunction(as_real(antiderivative, letter))
    target = RealFunction(as_real(integrand, letter))
    pairs = [(slope.at(x, 1), target.at(x)) for x in (*_SAMPLES, *(-v for v in _SAMPLES))]
    found = [(a, b) for a, b in pairs if math.isfinite(a) and math.isfinite(b)]
    return len(found) >= 2 and all(abs(a - b) < 1e-9 * (1 + abs(b)) for a, b in found)


def _no_constant(antiderivative: Any, integrand: Any, letter: Symbol) -> bool:
    """``antiderivative`` is one an answer writes with no constant added: the card's
    textbook form or SymPy's (``solve.antiderivative.antiderivative_forms``), as the reals
    read them (ln|x| is ln x where both are defined). A constant the reply chose (an
    initial value, a C) is no value the server can check; a family's constants are its
    ``shifts``, labelled."""
    try:
        forms = antiderivative_forms(integrand, letter)
    except (ValueError, TypeError, NotImplementedError, ZeroDivisionError):
        return False
    for form in forms:
        gap = RealFunction(as_real(antiderivative - form, letter))
        found = [v for v in (gap.at(x) for x in _SAMPLES) if math.isfinite(v)]
        if found and all(abs(v) < 1e-9 for v in found):
            return True
    return False


def _domain(
    curve: Curve, question: PlotQuestion, split: bool, written: Written | None
) -> list[Condition] | Literal[False] | None:
    """Where the curve is drawn, as conditions on x: the domain the question writes its
    formula with ("defined for 0 ≤ x ≤ 3 only", "for t ≥ 0", "0 < x < 2" with its ends left
    out), whether or not the description repeats it; else an interval of x the question
    states that the description gives. None for none: an interval the question does not
    state is a window the reply chose. False when that interval is a piece: the reply wrote
    one function as curves of one name (c011's x² + 1 "on [-10, -7]", 15 - 5x "on
    [-7, 4]"), and a whole parabola would stand for f."""
    own = question.domain_of(written.expr) if written is not None else None
    if own:
        return list(own)
    if curve.domain is None:
        return None
    start, end = (number(text) for text in curve.domain)
    held = stated_interval(start, end, question) if start is not None and end is not None else None
    if held is not None:
        low = Condition(">=" if held.low_closed else ">", held.low)
        return [low, Condition("<=" if held.high_closed else "<", held.high)]
    return False if split else None


def _search(domain: list[Condition] | None, question: PlotQuestion) -> tuple[float, float]:
    """Where places are looked for: the domain, as far out as the question reaches."""
    far = reach(question)
    lows = [float(c.value) for c in domain or [] if c.op in {">", ">="}]
    highs = [float(c.value) for c in domain or [] if c.op in {"<", "<="}]
    low = max(lows) if lows else -far
    high = min(highs) if highs else far
    if not lows and highs:
        low = min(low, high - far)
    if lows and not highs:
        high = max(high, low + far)
    return low, high


def _shift(text: str, question: PlotQuestion) -> Any | None:
    """A family's constant: one the question writes, or a small whole number."""
    constant = number(text)
    if constant is None:
        return None
    if any(same_number(v, constant) for v in question.values):
        return constant
    return constant if constant.is_Integer and abs(constant) <= _FAMILY_REACH else None


def _curves(
    curve: Curve, question: PlotQuestion, color: int, scene: Scene, split: bool
) -> list[DrawnCurve]:
    search = _search(None, question)
    name = curve.name or f"curve{color}"
    if curve.x and not curve.y and not curve.pieces:
        expr = formula(curve.x, _Y)
        if expr is None or not _written_sideways(expr, question):
            return []
        if expr.is_number and not _an_edge(expr, question):
            return []  # "the gradient at x = 3" names a point, no line x = 3
        label = equation_text("x", expr.subs(_Y, Symbol("y")))
        return [
            DrawnCurve(name, label, color, sideways=RealFunction(as_real(expr, _Y)), search=search)
        ]
    if curve.pieces:
        shape = pieces_shape(curve, question)
        return [] if shape is None else [DrawnCurve(name, "", color, shape, search=search)]
    found = _own_formula(curve.y, question)
    domain = _domain(curve, question, split, found.written if found else None)
    if found is None or domain is False:
        return []
    expr, letter, quantity = found.expr, found.letter, found.name
    search = _search(domain, question)
    raw = found.written.raw if found.written is not None else None
    stated = domain is not None
    scene.x_label = letter
    scene.y_label = quantity
    label = f"{quantity} = {formula_text(expr.subs(_X, Symbol(letter)))}"
    if found.antiderivative and curve.shifts:
        constants = [c for text in curve.shifts if (c := _shift(text, question)) is not None]
        return [
            DrawnCurve(
                name if i == 0 else f"{name}~{i}",
                f"C = {number_text(c)}",
                color + i,
                formula_shape(expr + c, domain),
                search=search,
                stated_domain=stated,
            )
            for i, c in enumerate(constants[:_MOST_CURVES])
        ]
    shown = label if len(label) <= _LABEL_CHARS else ""
    shape = formula_shape(expr, domain, raw)
    return [DrawnCurve(name, shown, color, shape, search=search, stated_domain=stated)]


def _through(line: Line, question: PlotQuestion, color: int) -> DrawnLine | None:
    """The line through two points the question writes, "the line through (-4, -1) and
    (5, 4)": its slope and offset worked out exactly."""
    ends: list[tuple[Any, Any]] = [
        (a, b)
        for a, b in ((number(p), number(q)) for p, q in line.through)
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
    # The server worked the line out: named only as the reply's working writes it.
    if x0 == x1:
        label = equation_text("x", x0)
        return DrawnLine(vertical=x0, label=label, color=color, held=(float(x0),))
    slope = (y1 - y0) / (x1 - x0)
    offset = y0 - slope * x0
    held = (float(slope), float(offset))
    return DrawnLine(slope, offset, label=line_text(slope, offset), color=color, held=held)


def _line(line: Line, question: PlotQuestion, color: int) -> DrawnLine | None:
    if line.through:
        return _through(line, question, color)
    if line.x and not line.y:
        at = number(line.x)
        # The question's own value, as it writes it (-1/2, never the reply's -0.5).
        own = [
            w.expr
            for w in question.formulas
            if at is not None and w.name == "x" and w.expr.is_number and same_value(w.expr, at)
        ]
        if not own or not _an_edge(own[0], question):
            return None
        return DrawnLine(vertical=own[0], label=equation_text("x", own[0]), color=color)
    expr = formula(line.y)
    slope = expr.diff(_X) if expr is not None else None
    if expr is None or slope is None or slope.free_symbols:
        return None
    written = any(
        w.name != "x"
        and (_a_level_line(w, question) or not expr.is_number)
        and same_value(w.expr, expr)
        for w in question.formulas
    )
    offset = expr.subs(_X, 0)
    label = equation_text("y", expr)
    if written:
        return DrawnLine(slope, offset, label=label, color=color)
    if not _through_two(expr, question):
        return None
    # A line through two stated points the reply worked out: named as its working writes it.
    return DrawnLine(slope, offset, label=label, color=color, held=(float(slope), float(offset)))


def _an_edge(at: Any, question: PlotQuestion) -> bool:
    """x = ``at`` is a line the question names ("the line x = 3", "bounded by ... and x = 2"),
    not a point it is said of ("the gradient at x = 3")."""
    return any(same_value(edge, at) for edge in question.edges)


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


def _stated_points_on(line: DrawnLine, question: PlotQuestion) -> list[tuple[float, float]]:
    """The points the question writes that a line runs through: the picture shows them
    ("the line through A(1, 2) and B(4, 8)" was drawn on [-2, 2])."""
    found: list[tuple[float, float]] = []
    for p, q in question.pairs:
        x, y = float(p), float(q)
        if line.vertical is not None:
            on = abs(float(line.vertical) - x) < 1e-9
        else:
            on = abs(float(line.slope) * x + float(line.offset) - y) < 1e-9 * (1 + abs(y))
        if on:
            found.append((x, y))
    return found


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
                scene.focus += _stated_points_on(line, question)
                color += 1
    for item in items:
        if isinstance(item, AxisNames):
            scene.x_label = _axis_name(item.x, scene.x_label, question) or scene.x_label
            scene.y_label = _axis_name(item.y, scene.y_label, question) or scene.y_label
