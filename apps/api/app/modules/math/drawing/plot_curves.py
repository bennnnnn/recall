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

import numpy as np
from sympy import E, Expr, Symbol, oo, pi, preorder_traversal, simplify

from app.modules.math.drawing.plot_check import reach, stated_interval
from app.modules.math.drawing.plot_items import (
    Average,
    AxisNames,
    Curve,
    Line,
    Rectangles,
    Shade,
)
from app.modules.math.drawing.plot_labels import (
    equation_text,
    formula_text,
    line_text,
    number_text,
)
from app.modules.math.drawing.plot_pieces import formula, formula_shape, pieces_shape
from app.modules.math.drawing.plot_question import PlotQuestion, Written
from app.modules.math.drawing.plot_reading import Condition, as_exact, number, plain, same_number
from app.modules.math.drawing.plot_scene import DrawnCurve, DrawnLine, Scene
from app.modules.math.drawing.real_curve import RealFunction, as_real
from app.modules.math.solve.antiderivative import antiderivative_forms
from app.modules.math.tool_check import parse_formula, same_value

_X, _Y = Symbol("x"), Symbol("y")
_MOST_CURVES = 5
_MOST_LINES = 4
_LABEL_CHARS = 48
# Where a curve in pieces is held to a formula the question writes: so many places in each
# piece, an endless one to this far.
_PIECE_SAMPLES, _PIECE_REACH = 41, 10.0
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
    if not isinstance(parsed, Expr):
        return None
    exact = as_exact(parsed, text, _constants(question))
    found = _own_expr(exact, question)
    if found is not None or exact.free_symbols != {_X}:
        return found
    # In x, the graph's own across, for the question's one letter: u5-088's v = 1.75x² + 8
    # for its v(t), the same curve.
    letters = {
        s for w in question.formulas if len(w.expr.free_symbols) == 1 for s in w.expr.free_symbols
    }
    others = letters - {_X}
    if len(others) != 1 or _X in letters:
        return None
    return _own_expr(exact.subs(_X, next(iter(others))), question)


def _constants(question: PlotQuestion) -> list[Any]:
    """The exact constants the question's formulas write (π, e, √2, 1/3)."""
    found = {pi, E}
    for written in question.formulas:
        found |= {
            part
            for part in preorder_traversal(written.expr)
            if part.is_number and not part.is_Integer and part.is_real
        }
    return sorted(found, key=str)


def _own_expr(parsed: Expr, question: PlotQuestion) -> _Own | None:
    if len(parsed.free_symbols) > 1:
        return None
    letter = next(iter(parsed.free_symbols), _X)
    for written in question.formulas:
        # "x = g(y)" is a curve on its side, drawn apart; "x = t² - 4t" is a position in t.
        sideways = written.name == "x" and not (
            written.expr.free_symbols - {_X, _Y} and letter != _X
        )
        if sideways or not written.expr.free_symbols <= {letter}:
            continue
        # "v(t)" names what an axis measures, as does a formula written with its unit
        # ("F = (9 - x/2) N"); "k(x)" only names a function.
        named = written.name not in {"y", ""} and bool(written.unit)
        quantity = named or (letter != _X and written.name not in _FUNCTION_NAMES)
        name = written.name if quantity else "y"
        if not parsed.free_symbols and not _a_level_line(written, question):
            continue  # "a = 3", "where y = 4" name values, never the line y = 3
        if same_value(written.expr, parsed) or _same_on_the_reals(written.expr, parsed, letter):
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


def _same_on_the_reals(written: Any, described: Any, letter: Symbol) -> bool:
    """The two formulas have the same value wherever either has one on the real line: the
    reply's x for (x³)^(1/3), whose principal branch SymPy keeps apart from x below 0."""
    if not written.free_symbols or not described.free_symbols:
        return False
    first = RealFunction(as_real(written, letter))
    second = RealFunction(as_real(described, letter))
    pairs = [(first.at(x), second.at(x)) for x in (*_SAMPLES, *(-v for v in _SAMPLES))]
    if any(math.isfinite(a) != math.isfinite(b) for a, b in pairs):
        return False
    found = [(a, b) for a, b in pairs if math.isfinite(a)]
    return len(found) >= 3 and all(abs(a - b) < 1e-9 * (1 + abs(b)) for a, b in found)


def _one_formula_for(drawn: DrawnCurve, question: PlotQuestion) -> str:
    """The legend of a curve described in pieces: the one formula the question writes that
    has each piece's value all along it, at its closed ends and at its single points
    (u5-071's y = |x| as -x and x), else none. f(x) = x² but 1 at 0 is no y = x²."""
    shape = drawn.shape
    # Only a whole curve: one whose pieces left out none (a piece's own formula is no
    # name for a function drawn in part).
    if shape is None or not shape.spans or not shape.complete:
        return ""
    checks: list[tuple[float, float]] = [(float(x), float(y)) for x, y in shape.dots]
    for span in shape.spans:
        low = -_PIECE_REACH if span.low == -oo else float(span.low)
        high = _PIECE_REACH if span.high == oo else float(span.high)
        if not low < high:
            return ""
        inside = np.linspace(low, high, _PIECE_SAMPLES)[1:-1]
        ends = [x for x, closed in ((low, span.low_closed), (high, span.high_closed)) if closed]
        for x in [*inside, *ends]:
            y = span.fn.at(float(x))
            if math.isfinite(y):
                checks.append((float(x), y))
    for written in question.formulas:
        if not written.defines or written.expr.free_symbols != {_X}:
            continue
        fn = RealFunction(as_real(written.expr, _X))
        if all(abs(fn.at(x) - y) < 1e-9 * (1 + abs(y)) for x, y in checks):
            label = f"y = {formula_text(written.expr)}"
            return label if len(label) <= _LABEL_CHARS else ""
    return ""


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
    curve: Curve,
    question: PlotQuestion,
    split: bool,
    written: Written | None,
    tasks: list[tuple[Any, Any]],
) -> list[Condition] | Literal[False] | None:
    """Where the curve is drawn, as conditions on x: the domain the question writes its
    formula with ("defined for 0 ≤ x ≤ 3 only", "for t ≥ 0", "0 < x < 2" with its ends left
    out, "on [0, 2]"), whether or not the description repeats it (``domain_of``). One
    written beside the formula that a region, rectangles or an average of the description
    stand on is theirs ("the average value of f(x) = x² on [0, 3]"), unless the question
    names it a domain or the description draws the curve on it too. None for none: an
    interval the question says of something else ("is decreasing for -1 < x < 1", "the area
    under it for 0 ≤ x ≤ 3") is a window the reply chose. False when the description's
    interval is a piece: the reply wrote one function as curves of one name (c011's x² + 1
    "on [-10, -7]", 15 - 5x "on [-7, 4]"), and a whole parabola would stand for f."""
    own = question.domain_of(written.expr) if written is not None else None
    start, end = (number(text) for text in curve.domain) if curve.domain else (None, None)
    described = [(start, end)] if start is not None and end is not None else []
    if own is not None and (
        own.named
        or not _a_task_interval(own.conditions, tasks)
        or _a_task_interval(own.conditions, described)
    ):
        return list(own.conditions)
    # A curve the question writes no formula for (an antiderivative) is drawn on an interval
    # of x the question states, as the description gives it (u5-008's family "for
    # 0 ≤ x ≤ 2π"); a formula it writes, only on the domain written to it.
    if curve.domain is None or not (split or written is None):
        return None
    held = stated_interval(start, end, question) if described else None
    if held is not None:
        low = Condition(">=" if held.low_closed else ">", held.low)
        return [low, Condition("<=" if held.high_closed else "<", held.high)]
    return False if split else None


def _a_task_interval(domain: tuple[Condition, ...], tasks: list[tuple[Any, Any]]) -> bool:
    lows = [c.value for c in domain if c.op in {">", ">="}]
    highs = [c.value for c in domain if c.op in {"<", "<="}]
    if len(lows) != 1 or len(highs) != 1:
        return False
    return any(same_number(lows[0], a) and same_number(highs[0], b) for a, b in tasks)


def _task_intervals(items: list[Any]) -> list[tuple[Any, Any]]:
    """The intervals the description's regions, rectangles and averages stand on."""
    found: list[tuple[Any, Any]] = []
    for item in items:
        if isinstance(item, (Shade, Rectangles, Average)):
            a, b = number(item.start), number(item.end)
            if a is not None and b is not None:
                found.append((a, b))
    return found


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
    return _a_family_constant(constant, question) if constant is not None else None


def _a_family_constant(constant: Any, question: PlotQuestion) -> Any | None:
    if any(same_number(v, constant) for v in question.values):
        return constant
    return constant if constant.is_Integer and abs(constant) <= _FAMILY_REACH else None


def _family_member(text: str, question: PlotQuestion) -> tuple[_Own | None, Any | None]:
    """A member of a family of antiderivatives the reply wrote as a curve of its own, an
    antiderivative and a constant ("5ln|x|/2 - 1" for c = -1): the antiderivative checked
    as any is, the constant one the question writes or a small whole number."""
    parsed = parse_formula(plain(text))
    if not isinstance(parsed, Expr) or not parsed.is_Add:
        return None, None
    constant, rest = parsed.as_coeff_Add()
    shift = _a_family_constant(constant, question) if constant != 0 else None
    found = _own_expr(rest, question) if shift is not None else None
    if found is None or not found.antiderivative:
        return None, None
    return found, shift


def _curves(
    curve: Curve,
    question: PlotQuestion,
    color: int,
    scene: Scene,
    split: bool,
    tasks: list[tuple[Any, Any]],
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
        # On the interval of y the question states and the description gives ("from y = 0
        # to y = 4"): u5-083's x = √y was drawn only to y ≈ 1.
        start, end = (number(t) for t in curve.domain) if curve.domain else (None, None)
        held = (
            stated_interval(start, end, question) if start is not None and end is not None else None
        )
        along = (float(held.low), float(held.high)) if held is not None else search
        fn = RealFunction(as_real(expr, _Y))
        return [
            DrawnCurve(
                name, label, color, sideways=fn, search=along, stated_domain=held is not None
            )
        ]
    if curve.pieces:
        shape = pieces_shape(curve, question)
        if shape is None:
            return []
        drawn = DrawnCurve(name, "", color, shape, search=search)
        drawn.label = _one_formula_for(drawn, question)
        return [drawn]
    found = _own_formula(curve.y, question)
    shift = None
    if found is None and question.antiderivatives:
        found, shift = _family_member(curve.y, question)
    if found is None:
        side = _a_side(curve, question, color, search)
        return [side] if side is not None else []
    domain = _domain(curve, question, split, found.written if found else None, tasks)
    if domain is False:
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
    if shift is not None:
        # One member of a family the reply wrote as its own curve ("F = 5ln|x|/2 - 1").
        label, shape = f"C = {number_text(shift)}", formula_shape(expr + shift, domain)
        return [DrawnCurve(name, label, color, shape, search=search, stated_domain=stated)]
    shown = label if len(label) <= _LABEL_CHARS else ""
    shape = formula_shape(expr, domain, raw)
    drawn = DrawnCurve(name, shown, color, shape, search=search, stated_domain=stated)
    drawn.antiderivative = found.antiderivative
    return [drawn]


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
    written = set(question.pairs)
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
    on = [(p, q) for p, q in question.pairs if expr.subs(_X, p) == q]
    return len({p for p, _q in on}) >= 2


def _a_side(
    curve: Curve, question: PlotQuestion, color: int, search: tuple[float, float]
) -> DrawnCurve | None:
    """A line described as a curve (a triangle's third side, u5-066's L3) through two points
    the question writes, as a line item through them is (``_through_two``): named only as
    the reply's working writes it."""
    expr = formula(curve.y) if curve.y and not curve.pieces else None
    slope = expr.diff(_X) if expr is not None else None
    if expr is None or slope is None or not slope.is_number or not _through_two(expr, question):
        return None
    offset = expr.subs(_X, 0)
    label = equation_text("y", expr)
    shape = formula_shape(expr, None)
    held = (float(slope), float(offset))
    return DrawnCurve(curve.name or f"curve{color}", label, color, shape, search=search, held=held)


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


def _drawn_as(curve: DrawnCurve) -> tuple[Any, ...]:
    """What a curve draws: its formula on each piece with the piece's ends, its dots, the
    way it is written, and the interval it is held to."""
    shape = curve.shape
    spans = (
        [(str(s.expr), s.low, s.low_closed, s.high, s.high_closed) for s in shape.spans]
        if shape
        else []
    )
    dots = [(x, str(y)) for x, y in shape.dots] if shape else []
    return (tuple(spans), tuple(dots), curve.sideways, curve.stated_domain and curve.search)


def _one_family(curve: DrawnCurve, member: DrawnCurve) -> bool:
    """``member`` is ``curve`` and a constant: two members of one family."""
    if curve.shape is None or member.shape is None:
        return False
    if len(curve.shape.spans) != 1 or len(member.shape.spans) != 1:
        return False
    return bool(simplify(member.shape.spans[0].expr - curve.shape.spans[0].expr).is_number)


def _unique(name: str, scene: Scene) -> str:
    found, k = name, 1
    while found in scene.curves:
        found, k = f"{name}~{k}", k + 1
    return found


def add_curves(items: list[Any], question: PlotQuestion, scene: Scene) -> None:
    color = 0
    names = Counter(item.name for item in items if isinstance(item, Curve) and item.name)
    tasks = _task_intervals(items)
    for item in items:
        if isinstance(item, Curve) and len(scene.curves) < _MOST_CURVES:
            for drawn in _curves(item, question, color, scene, names[item.name] > 1, tasks):
                # The same curve described twice is drawn once (a family's members differ).
                drawn_already = any(_drawn_as(c) == _drawn_as(drawn) for c in scene.curves.values())
                if len(scene.curves) < _MOST_CURVES and not drawn_already:
                    # A name is a label: two curves the reply named alike ("y", "F(x)") are
                    # two curves, the later one under a name of its own (g04 lost its second
                    # line, u5-005 two members of its family).
                    drawn.name = _unique(drawn.name, scene)
                    scene.curves[drawn.name] = drawn
                    color += 1
    # Beside members of its own family ("C = 1"), the antiderivative itself is "C = 0"; an
    # antiderivative of another function keeps its formula (x³ beside x² + C).
    members = [curve for curve in scene.curves.values() if curve.label.startswith("C = ")]
    for curve in scene.curves.values():
        if curve.antiderivative and any(_one_family(curve, member) for member in members):
            curve.label = "C = 0"
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
