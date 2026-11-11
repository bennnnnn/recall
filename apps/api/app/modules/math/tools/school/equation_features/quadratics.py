"""Features of a quadratic: the vertex and axis of symmetry, the discriminant, the sum
and product of the roots, the parameter that gives one, two or no real roots, and how
many solutions a polynomial equation has."""

from __future__ import annotations

import re
from typing import Any

from app.modules.math.schemas import MathIntent
from app.modules.math.tools.school.equation_features.forms import (
    _at,
    _bracket,
    _num,
    _point,
    _quadratic,
    _sides,
    _Solved,
    _symbols,
    _tex,
)
from app.services.workout import Workout, math_line, note_from_label


def _vertex(intent: MathIntent) -> _Solved | None:
    quadratic = _quadratic(intent, explicit_only=True)
    if quadratic is None:
        return None
    a, b, _c, expression = quadratic
    (x,) = _symbols("x")
    h = -b / (2 * a)
    k = expression.subs(x, h)
    answer = _point(h, k)
    workout = Workout(
        given=(math_line(f"y = {_tex(expression)}"),),
        find=(math_line(r"\left(h, k\right)", "vertex"),),
        formula=(math_line(r"h = -\frac{b}{2a}, \quad k = y(h)", "Vertex of a parabola"),),
        substitution=(
            math_line(rf"h = -\frac{{{_num(b)}}}{{2 \cdot {_bracket(a)}}} = {_num(h)}"),
            math_line(rf"k = {_at(expression, h)} = {_num(k)}", f"y at x = {_num(h)}"),
        ),
    )
    return workout, answer, [f"Vertex: ({h}, {k})"]


def _axis(intent: MathIntent) -> _Solved | None:
    quadratic = _quadratic(intent, explicit_only=True)
    if quadratic is None:
        return None
    a, b, _c, expression = quadratic
    h = -b / (2 * a)
    answer = f"x = {_num(h)}"
    workout = Workout(
        given=(math_line(f"y = {_tex(expression)}"),),
        find=(math_line("x = ?", "axis of symmetry"),),
        formula=(math_line(r"x = -\frac{b}{2a}", "Axis of symmetry"),),
        substitution=(math_line(rf"x = -\frac{{{_num(b)}}}{{2 \cdot {_bracket(a)}}} = {_num(h)}"),),
    )
    return workout, answer, [f"Axis of symmetry: x = {h}"]


def _discriminant(intent: MathIntent) -> _Solved | None:
    quadratic = _quadratic(intent, explicit_only=False)
    if quadratic is None:
        return None
    a, b, c, expression = quadratic
    value = b**2 - 4 * a * c
    answer = f"b^{{2}} - 4ac = {_num(value)}"
    workout = Workout(
        given=(math_line(f"{_tex(expression)} = 0"),),
        find=(math_line(r"\Delta", "discriminant"),),
        formula=(math_line(r"\Delta = b^2 - 4ac", "Discriminant"),),
        substitution=(
            math_line(
                rf"\Delta = {_bracket(b)}^2 - 4 \cdot {_bracket(a)} \cdot {_bracket(c)}"
                rf" = {_num(value)}"
            ),
        ),
    )
    return workout, answer, [f"Discriminant: {value}"]


def _roots_sum_or_product(intent: MathIntent, *, product: bool) -> _Solved | None:
    quadratic = _quadratic(intent, explicit_only=False)
    if quadratic is None:
        return None
    a, b, c, expression = quadratic
    if b**2 - 4 * a * c == 0:
        # One repeated root: "the sum of the roots" is 2r or r depending on who asks.
        return None
    if product:
        value = c / a
        answer = f"x_{{1}} x_{{2}} = {_num(value)}"
        formula = math_line(r"x_1 x_2 = \frac{c}{a}", "Product of the roots")
        working = rf"x_1 x_2 = \frac{{{_num(c)}}}{{{_num(a)}}} = {_num(value)}"
    else:
        value = -b / a
        answer = f"x_{{1}} + x_{{2}} = {_num(value)}"
        formula = math_line(r"x_1 + x_2 = -\frac{b}{a}", "Sum of the roots")
        working = rf"x_1 + x_2 = -\frac{{{_num(b)}}}{{{_num(a)}}} = {_num(value)}"
    workout = Workout(
        given=(math_line(f"{_tex(expression)} = 0"),),
        find=(math_line(r"x_1 x_2" if product else r"x_1 + x_2"),),
        formula=(formula,),
        substitution=(math_line(working),),
    )
    return workout, answer, [f"{'Product' if product else 'Sum'} of the roots: {value}"]


def _parameter(intent: MathIntent) -> _Solved | None:
    from sympy import Poly, S, expand, solveset

    from app.modules.math import solve as math_solve

    name = intent.variable
    if name in {"x", "e", "i"}:
        return None
    x, k = _symbols("x", name)
    lhs, rhs = _sides(intent, ["x", name])
    expression = expand(lhs - rhs)
    if not expression.free_symbols <= {x, k} or k not in expression.free_symbols:
        return None
    poly = Poly(expression, x)
    if poly.degree() != 2:
        return None
    a, b, c = poly.all_coeffs()
    if k in a.free_symbols or a == 0:
        # With the parameter in front of x^2 the equation can turn linear;
        # that case needs its own reading.
        return None
    discriminant = expand(b**2 - 4 * a * c)
    if k not in discriminant.free_symbols:
        return None
    relation = intent.comparator or "="
    if relation == "=":
        values = sorted(solveset(discriminant, k, domain=S.Reals), key=lambda v: float(v))
        if not values:
            return None
        answer = r" \text{ or } ".join(f"{name} = {_num(value)}" for value in values)
    else:
        result = math_solve.solve_inequality(str(discriminant), "0", name, relation)
        if len(result.solutions_latex) != 1:
            return None
        answer = result.solutions_latex[0]
    symbol = {"=": "=", ">": ">", "<": "<"}[relation]
    workout = Workout(
        given=(math_line(f"{_tex(expression)} = 0"),),
        find=(math_line(name),),
        formula=(math_line(rf"b^2 - 4ac {symbol} 0", "the condition on the discriminant"),),
        substitution=(
            math_line(
                rf"{_bracket(b)}^2 - 4 \cdot {_bracket(a)} \cdot {_bracket(c)} "
                rf"= {_tex(discriminant)} {symbol} 0"
            ),
            math_line(answer),
        ),
    )
    return workout, answer, [f"Discriminant {_tex(discriminant)} {symbol} 0: {answer}"]


_MAX_COUNT_DEGREE = 4


def _solution_count(intent: MathIntent) -> _Solved | None:
    """How many solutions one polynomial equation in one unknown has, whatever its letter.

    Without "real", the count must be the same over the reals and the complex
    numbers (``x^2 + 1 = 0`` has none or two, so it is declined). The working solves the
    equation, so the student sees the solutions the count is of (``x = \\pm …``).
    """
    from sympy import CRootOf, Poly, S, solveset

    from app.modules.math import solve as math_solve

    unknowns = math_solve.guess_variables(f"{intent.lhs} = {intent.rhs}")
    if len(unknowns) != 1:
        return None
    (name,) = unknowns
    (x,) = _symbols(name)
    lhs, rhs = _sides(intent, [name])
    expression = lhs - rhs
    if not expression.free_symbols <= {x}:
        return None
    poly = Poly(expression, x)
    if poly.degree() > _MAX_COUNT_DEGREE:
        return None
    real = intent.trial_outcome == "real"
    reals = solveset(expression, x, domain=S.Reals)
    complexes = solveset(expression, x, domain=S.Complexes)
    if reals == S.Reals:
        if not real and complexes != S.Complexes:
            return None
        answer = r"\text{infinitely many}"
        rows = [
            *_one_side_rows(lhs, rhs, poly, name),
            math_line(rf"\text{{true for every }} {name}"),
        ]
    else:
        if not hasattr(reals, "__len__") or not hasattr(complexes, "__len__"):
            return None
        if not real and len(reals) != len(complexes):
            return None
        if any(root.has(CRootOf) for root in reals):
            # Roots no radical writes: the working could not show them.
            return None
        answer = str(len(reals))
        if reals:
            rows = _solving_rows(lhs, rhs, name, sorted(reals, key=float))
        else:
            none = r"\text{no real solutions}" if real else r"\text{no solutions}"
            rows = [*_one_side_rows(lhs, rhs, poly, name), math_line(none)]
    workout = Workout(
        given=(math_line(f"{_tex(lhs)} = {_tex(rhs)}"),),
        find=(math_line(r"\text{number of " + ("real " if real else "") + "solutions}"),),
        steps=tuple(rows),
    )
    return workout, answer, [f"Number of solutions: {answer}"]


def _one_side_rows(lhs: Any, rhs: Any, poly: Any, name: str) -> list[str]:
    """Everything on one side, and a quadratic's discriminant: why there is no solution, or
    no end to them, when there is nothing to solve for."""
    rows: list[str] = []
    if rhs != 0 or lhs != poly.as_expr():
        constant = poly.degree() == 0 and poly.as_expr() != 0
        note = f"never true, whatever {name} is" if constant else "everything on one side"
        rows.append(math_line(f"{_tex(poly.as_expr())} = 0", note))
    if poly.degree() == 2:
        a, b, c = poly.all_coeffs()
        discriminant = b**2 - 4 * a * c
        sign = ">" if discriminant > 0 else ("=" if discriminant == 0 else "<")
        rows.append(
            math_line(rf"\Delta = b^2 - 4ac = {_num(discriminant)} {sign} 0", "discriminant")
        )
    return rows


def _solving_rows(lhs: Any, rhs: Any, name: str, solutions: list[Any]) -> list[str]:
    """The equation solved: the solve card's own trace, a move on both sides and its
    "Simplify" read as one row, ending on the solutions themselves."""
    from app.modules.math.solve.key_steps import equation_key_steps
    from app.modules.math.solve.root_latex import compact_root_answer_lines

    rows: list[tuple[str, str]] = []
    branched = solved = False
    for step in equation_key_steps(lhs, rhs, name):
        solved = step.label == "Simplify"
        if step.branch is not None:
            # One move per factor ("add 2 to both sides of the first equation"):
            # the result after them is each factor solved.
            branched = True
        elif solved and branched:
            rows.append(("solve each equation", step.formula))
            branched = False
        elif solved and rows and "both sides" in rows[-1][0]:
            rows[-1] = (rows[-1][0], step.formula)
        else:
            rows.append((note_from_label(step.label), step.formula))
    if not solved:
        # No trace, or one that stops before the values: the solutions, as the solve
        # card writes them (``\approx`` where a root is only written to six figures).
        lines = [
            re.sub(r" = (?=-?\d+\.\d)", r" \\approx ", line, count=1)
            for line in compact_root_answer_lines(name, solutions)
        ]
        first = "the solution" if len(solutions) == 1 else "the solutions"
        rows.append(("simplify" if rows else first, r" \text{ or } ".join(lines)))
    return [math_line(formula, note) for note, formula in rows]
