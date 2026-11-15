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

import re
from dataclasses import dataclass, field
from typing import Any

from sympy import Expr, Symbol, nsimplify, oo, simplify

from app.modules.math.drawing.plot_items import Curve
from app.modules.math.drawing.plot_question import Clause, Condition, PlotQuestion, plain
from app.modules.math.drawing.real_curve import RealFunction, as_real
from app.modules.math.tool_check import parse_formula, same_value

_X = Symbol("x")
_OPS = re.compile(r"(<=|>=|!=|<|>|=)")
_FLIPPED = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "=", "!=": "!="}
_LOWER, _UPPER = frozenset({">", ">="}), frozenset({"<", "<="})


@dataclass(frozen=True)
class Span:
    """One formula over an interval of x; an end is a number or ±∞."""

    fn: RealFunction
    expr: Any
    low: Any = -oo
    low_closed: bool = False
    high: Any = oo
    high_closed: bool = False


@dataclass
class Shape:
    spans: list[Span] = field(default_factory=list)
    # Values the question gives the function at single points ("f(1) = 5").
    dots: list[tuple[Any, Any]] = field(default_factory=list)


def formula(text: str, variable: Symbol = _X) -> Any | None:
    """A formula the reply wrote, in ``variable`` alone."""
    parsed = parse_formula(plain(text))
    if not isinstance(parsed, Expr) or not parsed.free_symbols <= {variable}:
        return None
    return parsed


def value(text: str) -> Any | None:
    parsed = parse_formula(plain(text))
    return parsed if isinstance(parsed, Expr) and parsed.is_number and parsed.is_real else None


def read_condition(text: str) -> list[Condition] | None:
    """ "-5 < x <= -2" as [(>, -5), (<=, -2)], each comparison with x on the left."""
    parts = [part.strip() for part in _OPS.split(plain(text))]
    if len(parts) not in {3, 5} or "x" not in parts[::2]:
        return None
    found: list[Condition] = []
    for i in range(1, len(parts) - 1, 2):
        left, op, right = parts[i - 1], parts[i], parts[i + 1]
        if left == "x" and (number := value(right)) is not None:
            found.append(Condition(op, number))
        elif right == "x" and (number := value(left)) is not None:
            found.append(Condition(_FLIPPED[op], number))
        else:
            return None
    return found


def _same_number(a: Any, b: Any) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-12 * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return False


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
            if name in bound and not _same_number(bound[name], own.value):
                return False
            bound[name] = own.value
        elif not _same_number(own.value, written.value):
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
            if any(_same_number(a, at) and same_value(b, expr) for a, b in clause.point_values):
                return True
    return False


def _spans(expr: Any, conditions: list[Condition]) -> list[Span]:
    fn = RealFunction(as_real(expr, _X))
    low, low_closed, high, high_closed = -oo, False, oo, False
    cuts: list[Any] = []
    for c in conditions:
        if c.op in _LOWER and (low == -oo or c.value > low):
            low, low_closed = c.value, c.op == ">="
        elif c.op in _UPPER and (high == oo or c.value < high):
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
        left = [s for s in spans if s.high != oo and _same_number(s.high, at)]
        right = [s for s in spans if s.low != -oo and _same_number(s.low, at)]
        if not left or not right:
            return False
        exact = nsimplify(at)
        for a in left:
            for b in right:
                if simplify(a.expr.subs(_X, exact) - b.expr.subs(_X, exact)) != 0:
                    return False
    return True


def pieces_shape(curve: Curve, question: PlotQuestion) -> Shape | None:
    """The pieces of ``curve`` the question writes, or None when none is, or when a letter's
    value is not where its pieces meet (that picture would be wrong, not just short)."""
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
    if not shape.spans or not _letters_meet(shape.spans, letters):
        return None
    return shape


def formula_shape(expr: Any, domain: tuple[Any, Any] | None) -> Shape:
    fn = RealFunction(as_real(expr, _X))
    if domain is None:
        return Shape([Span(fn, expr)])
    return Shape([Span(fn, expr, domain[0], True, domain[1], True)])
