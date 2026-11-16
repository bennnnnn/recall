"""A curve as the spans of x it is drawn on, held to the question piece by piece.

A curve written as one formula is one span: every x, or the interval the question states.
A function defined in pieces is drawn only from pieces the question writes: each piece's
formula and its whole condition come from one clause of the question ("f(x) = -0.6 if -5 <
x ≤ -2"), with the same ends and the same strictness, so an open circle is never drawn
where the question includes the end. An end the question gives as a letter ("x < a",
"a ≤ x ≤ b") takes the reply's value only when the two pieces meet there, which is what
makes the function continuous, as such a question asks.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sympy import Expr, Pow, Symbol, log, nsimplify, oo, preorder_traversal, simplify

from app.modules.math.drawing.curve_features import exact_xs, snapped, zeros
from app.modules.math.drawing.plot_items import Curve
from app.modules.math.drawing.plot_question import Clause, PlotQuestion
from app.modules.math.drawing.plot_reading import (
    LOWER,
    UPPER,
    Condition,
    conditions,
    plain,
    same_number,
)
from app.modules.math.drawing.real_curve import RealFunction, as_real
from app.modules.math.solve.graph_sampling import side, singular_xs
from app.modules.math.tool_check import parse_formula, same_value

_X = Symbol("x")


@dataclass(frozen=True)
class Span:
    """One formula over an interval of x; an end is a number or ±∞."""

    fn: RealFunction
    expr: Any
    low: Any = -oo
    low_closed: bool = False
    high: Any = oo
    high_closed: bool = False


def end_value(span: Span, end: Any, closed: bool, inward: int) -> float | None:
    """The value a span reaches at its end: its own there when it holds the end, else the
    one it settles on from inside; None where it runs off to infinity (1/x at 0, ln x at 0)
    or has none, so no circle or window is set at 10⁷ or at NaN."""
    x = float(end)
    if closed:
        y = span.fn.at(x)
        if math.isfinite(y):
            return y
    near = side(span.fn.values, x, inward)
    return near.value if near.kind == "finite" else None


@dataclass
class Shape:
    spans: list[Span] = field(default_factory=list)
    # Values the question gives the function at single points ("f(1) = 5").
    dots: list[tuple[Any, Any]] = field(default_factory=list)
    # Every piece the question defines is drawn: an end a piece leaves out is then a gap.
    # Drawn from some pieces only, the value there may be a missing piece's (t09).
    complete: bool = True


def formula(text: str, variable: Symbol = _X) -> Any | None:
    """A formula the reply wrote, in ``variable`` alone."""
    parsed = parse_formula(plain(text))
    if not isinstance(parsed, Expr) or not parsed.free_symbols <= {variable}:
        return None
    return parsed


def read_condition(text: str) -> list[Condition] | None:
    """ "-5 < x <= -2" as [(>, -5), (<=, -2)], each comparison with x on the left: the
    question's own reading (``plot_reading.conditions``), every bound a number."""
    found = conditions(plain(text))
    return found if found and all(c.value.is_number for c in found) else None


def _bind(mine: list[Condition], clause: Clause, letters: dict[str, Any]) -> bool:
    """Every comparison of the piece is one of the clause's, and the clause has no other."""
    if len(mine) != len(clause.conditions):
        return False
    bound = dict(letters)
    for own, written in zip(
        sorted(mine, key=lambda c: c.op), sorted(clause.conditions, key=lambda c: c.op), strict=True
    ):
        if own.op != written.op:
            return False
        if isinstance(written.value, Symbol):
            name = str(written.value)
            if name in bound and not same_number(bound[name], own.value):
                return False
            bound[name] = own.value
        elif not same_number(own.value, written.value):
            return False
    letters.update(bound)
    return True


def _written_piece(
    expr: Any, mine: list[Condition], question: PlotQuestion, letters: dict[str, Any]
) -> bool:
    for clause in question.clauses:
        if any(same_value(expr, written) for written in clause.formulas):
            if _bind(mine, clause, letters):
                return True
        if len(mine) == 1 and mine[0].op == "=":
            at = mine[0].value
            if any(same_number(a, at) and same_value(b, expr) for a, b in clause.point_values):
                return True
    return False


def _spans(expr: Any, conditions: list[Condition]) -> list[Span]:
    fn = RealFunction(as_real(expr, _X))
    low, low_closed, high, high_closed = -oo, False, oo, False
    cuts: list[Any] = []
    for c in conditions:
        if c.op in LOWER and (low == -oo or c.value > low):
            low, low_closed = c.value, c.op == ">="
        elif c.op in UPPER and (high == oo or c.value < high):
            high, high_closed = c.value, c.op == "<="
        elif c.op == "!=":
            cuts.append(c.value)
    spans = [Span(fn, expr, low, low_closed, high, high_closed)]
    for cut in sorted(cuts):
        last = spans.pop()
        spans += [
            Span(fn, expr, last.low, last.low_closed, cut, False),
            Span(fn, expr, cut, False, last.high, last.high_closed),
        ]
    return [s for s in spans if s.low == -oo or s.high == oo or s.low < s.high]


def _letters_meet(spans: list[Span], letters: dict[str, Any]) -> bool:
    """Each letter's value is where the pieces on its two sides meet."""
    for at in letters.values():
        left = [s for s in spans if s.high != oo and same_number(s.high, at)]
        right = [s for s in spans if s.low != -oo and same_number(s.low, at)]
        if not left or not right:
            return False
        exact = nsimplify(at)
        for a in left:
            for b in right:
                if simplify(a.expr.subs(_X, exact) - b.expr.subs(_X, exact)) != 0:
                    return False
    return True


def _clause_formula(clause: Clause) -> Any | None:
    """The one formula a clause defines, a value it gives at a point ("f(1) = 5") aside;
    None when it holds none or more than one."""
    given = [b for _a, b in clause.point_values]
    found: list[Any] = []
    for expr in clause.formulas:
        if expr.is_number and any(same_value(expr, b) for b in given):
            continue
        if not any(same_value(expr, seen) for seen in found):
            found.append(expr)
    return found[0] if len(found) == 1 else None


def _question_shape(question: PlotQuestion, letters: dict[str, Any]) -> Shape | None:
    """The function the question defines in pieces, clause by clause, its letters at the
    reply's values; None when it defines none, or a clause is not clear."""
    shape = Shape()
    for clause in question.clauses:
        shape.dots += list(clause.point_values)
        if not clause.conditions:
            continue
        expr = _clause_formula(clause)
        if expr is None or not isinstance(expr, Expr) or not expr.free_symbols <= {_X}:
            if clause.formulas:
                return None
            continue
        conditions: list[Condition] = []
        for c in clause.conditions:
            at = letters.get(str(c.value)) if isinstance(c.value, Symbol) else c.value
            if at is None:
                return None
            conditions.append(Condition(c.op, at))
        if len(conditions) == 1 and conditions[0].op == "=":
            shape.dots.append((conditions[0].value, expr))
        else:
            shape.spans += _spans(expr, conditions)
    pieces = len(shape.spans) + len(shape.dots)
    return shape if shape.spans and pieces >= 2 else None


def _one_formula(question: PlotQuestion) -> Shape | None:
    """The question's one formula, when the reply wrote it in pieces it does not (|ln x| as
    -ln x and ln x, x²|9 - x²|/(3 - x) as two cubics): drawn whole, its breaks found."""
    found: list[Any] = []
    for written in question.formulas:
        expr = written.expr
        if written.name == "x" or not expr.free_symbols or not expr.free_symbols <= {_X}:
            continue
        if not any(same_value(expr, seen) for seen in found):
            found.append(expr)
    return formula_shape(found[0], None) if len(found) == 1 else None


def _value_on(shape: Shape, x: float) -> float | None:
    for span in shape.spans:
        low = span.low == -oo or x > float(span.low)
        high = span.high == oo or x < float(span.high)
        if low and high:
            value = span.fn.at(x)
            return value if math.isfinite(value) else None
    return None


def _describes(curve: Curve, shape: Shape) -> bool:
    """Every piece the reply wrote is the question's function where it holds (4x + 4 for
    4|x² - 1|/(x - 1) when x > 1 is), and at least one is."""
    agreed = 0
    for piece in curve.pieces:
        expr, mine = formula(piece.y), read_condition(piece.when)
        if expr is None or mine is None:
            continue
        own = RealFunction(as_real(expr, _X))
        for x in _inside_points(mine):
            want, have = _value_on(shape, x), own.at(x)
            if want is None or not math.isfinite(have):
                continue
            if abs(want - have) > 1e-9 * (1 + abs(want)):
                return False
            agreed += 1
    return agreed > 0


def _inside_points(conditions: list[Condition]) -> list[float]:
    lows = [float(c.value) for c in conditions if c.op in LOWER]
    highs = [float(c.value) for c in conditions if c.op in UPPER]
    if lows and highs:
        low, high = max(lows), min(highs)
        return [low + (high - low) * t for t in (0.25, 0.5, 0.75)]
    if highs:
        return [min(highs) - 0.5, min(highs) - 2.0]
    return [max(lows) + 0.5, max(lows) + 2.0] if lows else []


def pieces_shape(curve: Curve, question: PlotQuestion) -> Shape | None:
    """The function in pieces the reply describes: the question's own, clause by clause,
    when the reply's pieces are it where they hold; else the reply's pieces the question
    writes. None when no piece is the question's, or when a letter's value is not where its
    pieces meet (that picture would be wrong, not just short)."""
    shape = Shape()
    letters: dict[str, Any] = {}
    for piece in curve.pieces:
        expr = formula(piece.y)
        mine = read_condition(piece.when)
        if expr is None or mine is None or not _written_piece(expr, mine, question, letters):
            continue
        if len(mine) == 1 and mine[0].op == "=":
            shape.dots.append((mine[0].value, expr))
        else:
            shape.spans += _spans(expr, mine)
    shape.complete = False
    whole = _question_shape(question, letters) or _one_formula(question)
    if whole is not None and _describes(curve, whole):
        shape = whole
    if not shape.spans or not _letters_meet(shape.spans, letters):
        return None
    return shape


def formula_shape(expr: Any, domain: Sequence[Condition] | None, raw: Any = None) -> Shape:
    """One formula on the domain it is drawn on (its ends held or left out as the conditions
    say: "0 < x < 2" ends in open circles), and only where the formula as written has values
    (``raw``: e^(ln x) none below 0, x/x none at 0)."""
    conditions = [*(domain or []), *(_as_written_conditions(expr, raw) if raw is not None else [])]
    if not conditions:
        return Shape([Span(RealFunction(as_real(expr, _X)), expr)])
    return Shape(_spans(expr, conditions))


# How far either side of 0 a formula as written is checked for values its simplified form has.
_WRITTEN_REACH = 50.0


def _written_rules(raw: Any) -> list[tuple[str, Any]]:
    """What the formula as written asks of x, read from its own tree before SymPy
    simplifies it: a logarithm's argument above 0, an even root's at least 0, a power below
    0 or of 0 its base not 0 (x/x is x·x⁻¹; x⁰ has no value at 0). Each argument is read on
    its own, so e^(ln x) keeps its ln x > 0 though SymPy reads the whole as x; an odd root
    (x^(2/3)) asks nothing."""
    rules: list[tuple[str, Any]] = []
    for node in preorder_traversal(raw):
        if isinstance(node, log):
            rules.append((">", node.args[0].doit()))
        elif isinstance(node, Pow):
            power = node.exp.doit()
            if not power.is_Rational:
                continue
            if power.is_negative or power.is_zero:
                rules.append(("!=", node.base.doit()))  # x/x and x⁰ have none at 0
            if power.q % 2 == 0:
                rules.append((">=", node.base.doit()))
    return rules


def _runs_through(fn: RealFunction, x: float) -> bool:
    sides = [side(fn.values, x, direction) for direction in (-1, 1)]
    return all(found.kind == "finite" for found in sides)


def _as_written_conditions(expr: Any, raw: Any) -> list[Condition]:
    """Where ``raw``, a formula as the question writes it, has no value though ``expr``, its
    simplified form, does: where a denominator it writes is 0 (x/x at 0), and beyond a bound
    it has values only on one side of (e^(ln x) below 0, (√x)² below 0)."""
    letters = list(raw.free_symbols)
    if len(letters) != 1:
        return []
    found: list[Condition] = []
    xs = np.linspace(-_WRITTEN_REACH, _WRITTEN_REACH, 2001)
    has = np.ones(xs.shape, dtype=bool)
    simple = RealFunction(as_real(expr, _X))
    # Where the simplified formula breaks itself (1/x at 0), its own breaks say so.
    own = [float(v) for v in singular_xs(expr, _X, -_WRITTEN_REACH, _WRITTEN_REACH)]
    bounds: list[tuple[Any, str]] = []
    for op, arg in _written_rules(raw):
        part = RealFunction(as_real(arg, letters[0]))
        exact = exact_xs(part)
        edges = [
            snapped(x, exact, part.expr)
            for x in zeros(part.values, -_WRITTEN_REACH, _WRITTEN_REACH)
        ]
        if op == "!=":
            # A hole only where the simplified formula runs on through (x/x at 0); where it
            # runs off to infinity (1/sin x at kπ) its own breaks say so.
            found += [
                Condition("!=", at)
                for at in edges
                if all(abs(float(at) - x) > 1e-9 for x in own) and _runs_through(simple, float(at))
            ]
            continue
        values = part.values(xs)
        has &= (values > 0) if op == ">" else (values >= 0)
        bounds += [(at, op) for at in edges]
    real = np.isfinite(simple.values(xs))
    kept = np.flatnonzero(has & real)
    if not (real & ~has).any() or not kept.size or not has[kept[0] : kept[-1] + 1].all():
        return found  # nothing lost, or values lost inside: no one bound says where
    for edge, op, out in ((kept[0], ">", -1), (kept[-1], "<", 1)):
        if not 0 <= edge + out < len(xs):
            continue
        low, high = sorted((float(xs[edge + out]), float(xs[edge])))
        near = [(at, rule) for at, rule in bounds if low - 1e-9 <= float(at) <= high + 1e-9]
        if near:
            at, rule = near[0]
            closed = rule == ">=" and math.isfinite(simple.at(float(at)))
            found.append(Condition(op + "=" if closed else op, at))
    return found
