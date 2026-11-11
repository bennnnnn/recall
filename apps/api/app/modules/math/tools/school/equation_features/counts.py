"""How many solutions one equation in one unknown has, whatever its letter.

The equation is a polynomial, or one over a denominator (``x^2/x = 0``), of degree 4 at
most. A value that makes a denominator of the written equation zero is no solution, as
the solve card says (``x \\ne 0``). The count is over the set the request names
(``count_conditions``: "in [0, 5]", "for x > 0", "positive"); without one and without
"real", it must be the same over the reals and the complex numbers (``x^2 + 1 = 0`` has
none or two, so it is declined). Distinct values are counted, as school does, unless the
request counts multiplicity. The working solves the equation, so the student sees the
solutions the count is of (``x = \\pm …``), and names a repeated root.
"""

from __future__ import annotations

import re
from typing import Any

from app.modules.math.schemas import EquationInput, MathIntent
from app.modules.math.tools.school.equation_features.parsing import equation_sides, parse_side
from app.services.workout import Workout, math_line, note_from_label

_MAX_DEGREE = 4
# Counted below the readers' cycle: ``forms`` imports back into the school readers, so
# this module reads with ``parsing`` and writes TeX with SymPy directly.
_Counted = tuple[Workout, str, list[str]]
_REPEATS = {2: ("double", "twice"), 3: ("triple", "three times"), 4: ("quadruple", "four times")}


def solution_count(intent: MathIntent) -> _Counted | None:
    from sympy import Poly, Symbol, together

    from app.modules.math import solve as math_solve
    from app.modules.math.solve.equation_conditions import original_domain_conditions

    unknowns = math_solve.guess_variables(f"{intent.lhs} = {intent.rhs}")
    if len(unknowns) != 1:
        return None
    (name,) = unknowns
    x = Symbol(name)
    lhs, rhs = equation_sides(intent, [name])
    numerator, denominator = together(lhs - rhs).as_numer_denom()
    if not (numerator.free_symbols | denominator.free_symbols) <= {x}:
        return None
    poly = Poly(numerator, x)
    if poly.degree() > _MAX_DEGREE:
        return None
    written = EquationInput(lhs=intent.lhs or "", rhs=intent.rhs or "", variables=[name])
    excluded, exclusions = original_domain_conditions(written, x)
    counted = set((intent.trial_outcome or "").split())
    regions = _regions(intent)
    if regions is None:
        return None
    if poly.is_zero:
        found = _identity(name, regions, exclusions)
    else:
        found = _finite(intent, poly, x, excluded, regions, counted)
    if found is None:
        return None
    answer, steps = found
    if exclusions:
        steps = [math_line(r",\; ".join(exclusions), "a denominator cannot be zero"), *steps]
    asked = r"\text{number of " + ("real " if "real" in counted else "") + "solutions}"
    if regions:
        asked += rf",\; {name} \in {_tex(regions[0])}"
    workout = Workout(
        given=(math_line(_written(intent, name) or f"{_tex(lhs)} = {_tex(rhs)}"),),
        find=(math_line(asked),),
        steps=tuple(steps),
    )
    return workout, answer, [f"Number of solutions: {answer}"]


def _regions(intent: MathIntent) -> list[Any] | None:
    """The interval asked about, less the points a condition removes, in each reading of
    its ends ("between 0 and 5": open and closed); [] when the request names none, None
    when a bound does not parse."""
    from sympy import FiniteSet, Interval, S, oo

    removed = FiniteSet(*(parse_side(point, []) for point in intent.arithmetic_operands or []))
    if intent.integral_lower is None and intent.integral_upper is None:
        # "for x != 2" alone: every real number but the points it names.
        return [S.Reals - removed] if removed else []
    low = -oo if intent.integral_lower is None else parse_side(intent.integral_lower, [])
    high = oo if intent.integral_upper is None else parse_side(intent.integral_upper, [])
    if not (low.is_comparable or low == -oo) or not (high.is_comparable or high == oo):
        return None
    ends = [
        [False, True] if comparator == "?" else [comparator != "<="]
        for comparator in (intent.comparator, intent.comparator_upper)
    ]
    return [
        Interval(low, high, left_open, right_open) - removed
        for left_open in ends[0]
        for right_open in ends[1]
    ]


def _identity(name: str, regions: list[Any], exclusions: list[str]) -> tuple[str, list[str]] | None:
    """``2(x + 1) = 2x + 2``: true wherever it is defined."""
    if any(region.measure == 0 for region in regions):
        return None
    rows = [math_line("0 = 0", "everything on one side")]
    where = rf"\text{{true for every }} {name}"
    if regions:
        where += rf" \in {_tex(regions[0])}"
    if exclusions:
        where += rf",\; {r',\; '.join(exclusions)}"
    return r"\text{infinitely many}", [*rows, math_line(where)]


def _finite(
    intent: MathIntent,
    poly: Any,
    x: Any,
    excluded: list[Any],
    regions: list[Any],
    counted: set[str],
) -> tuple[str, list[str]] | None:
    from sympy import CRootOf, S, roots, solveset

    from app.modules.math.solve.root_latex import expr_equal

    numerator = poly.as_expr()
    reals = solveset(numerator, x, domain=S.Reals)
    complexes = solveset(numerator, x, domain=S.Complexes)
    if not hasattr(reals, "__len__") or not hasattr(complexes, "__len__"):
        return None
    if any(root.has(CRootOf) for root in reals):
        # Roots no radical writes: the working could not show them.
        return None
    multiplicities = roots(poly)
    if "multiplicity" in counted and (excluded or sum(multiplicities.values()) != poly.degree()):
        return None

    def kept(values: Any) -> list[Any]:
        return [value for value in values if not any(expr_equal(value, out) for out in excluded)]

    def times(value: Any) -> int:
        return next((m for root, m in multiplicities.items() if expr_equal(root, value)), 1)

    candidates = sorted(kept(reals), key=float)
    if not regions and "real" not in counted and len(candidates) != len(kept(complexes)):
        return None
    with_multiplicity = "multiplicity" in counted
    counts = {
        sum(
            times(value) if with_multiplicity else 1
            for value in candidates
            if region.contains(value) == S.true
        )
        for region in regions or [S.Reals]
    }
    if len(counts) != 1:
        # "between 0 and 5" with a root at 0 or 5: the count depends on the reading.
        return None
    answer = str(counts.pop())
    name = str(x)
    if not reals:
        none = r"\text{no real solutions}" if "real" in counted else r"\text{no solutions}"
        return answer, [*_one_side_rows(intent, poly, name), math_line(none)]
    if excluded:
        rows = [
            math_line(
                f"{_tex(_cleared(intent, name) or numerator)} = 0",
                "multiply both sides by the denominator",
            ),
            math_line(_listed(name, sorted(reals, key=float)), "solve"),
        ]
        dropped = [value for value in reals if value not in candidates]
        if dropped:
            out = ", ".join(f"{name} = {_tex(value)}" for value in dropped)
            rows.append(math_line(_listed(name, candidates), f"{out} is excluded"))
    else:
        rows = _solving_rows(intent, name, candidates)
    if regions:
        inside = [value for value in candidates if regions[0].contains(value) == S.true]
        noun = "the solution" if len(inside) == 1 else "the solutions"
        rows.append(math_line(_listed(name, inside), f"{noun} in {_region_words(regions)}"))
        candidates = inside
    for value in candidates:
        repeat = _REPEATS.get(times(value))
        if repeat is not None:
            word, how_often = repeat
            often = how_often if with_multiplicity else "once"
            rows.append(math_line(f"{name} = {_tex(value)}", f"a {word} root, counted {often}"))
    return answer, rows


def _written(intent: MathIntent, name: str) -> str | None:
    """The equation as the student typed it: ``\\frac{x^{2}}{x} = 0``, not SymPy's ``x = 0``."""
    from app.modules.math.solve.key_steps import written_side

    sides = [written_side(text or "", [name]) for text in (intent.lhs, intent.rhs)]
    if sides[0] is None or sides[1] is None:
        return None
    return f"{sides[0][1]} = {sides[1][1]}"


def _cleared(intent: MathIntent, name: str) -> Any | None:
    """The typed equation times its denominators, before anything cancels: ``x^2 = 0``."""
    from sympy import expand

    from app.modules.math.solve.key_steps import written_side

    left = written_side(intent.lhs or "", [name])
    right = written_side(intent.rhs or "", [name])
    if left is None or right is None:
        return None
    top_l, bottom_l = left[0].as_numer_denom()
    top_r, bottom_r = right[0].as_numer_denom()
    return expand(top_l * bottom_r - top_r * bottom_l)


def _region_words(regions: list[Any]) -> str:
    from sympy import latex

    return f"${latex(regions[0])}$"


def _listed(name: str, values: list[Any]) -> str:
    from app.modules.math.solve.root_latex import compact_root_answer_lines

    if not values:
        return r"\text{none}"
    lines = [
        # ``\approx`` where a root is only written to six figures.
        re.sub(r" = (?=-?\d+\.\d)", r" \\approx ", line, count=1)
        for line in compact_root_answer_lines(name, values)
    ]
    return r" \text{ or } ".join(lines)


def _one_side_rows(intent: MathIntent, poly: Any, name: str) -> list[str]:
    """Everything on one side, and a quadratic's discriminant: why there is no solution
    when there is nothing to solve for."""
    lhs, rhs = equation_sides(intent, [name])
    rows: list[str] = []
    if rhs != 0 or lhs != poly.as_expr():
        constant = poly.degree() == 0
        note = f"never true, whatever {name} is" if constant else "everything on one side"
        rows.append(math_line(f"{_tex(poly.as_expr())} = 0", note))
    if poly.degree() == 2:
        a, b, c = poly.all_coeffs()
        discriminant = b**2 - 4 * a * c
        sign = ">" if discriminant > 0 else ("=" if discriminant == 0 else "<")
        rows.append(
            math_line(rf"\Delta = b^2 - 4ac = {_tex(discriminant)} {sign} 0", "discriminant")
        )
    return rows


def _solving_rows(intent: MathIntent, name: str, solutions: list[Any]) -> list[str]:
    """The equation solved: the solve card's own trace, a move on both sides and its
    "Simplify" read as one row, ending on the solutions themselves."""
    from app.modules.math.solve.key_steps import equation_key_steps

    lhs, rhs = equation_sides(intent, [name])
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
        # No trace, or one that stops before the values: the solutions as the solve
        # card writes them.
        first = "the solution" if len(solutions) == 1 else "the solutions"
        rows.append(("simplify" if rows else first, _listed(name, solutions)))
    return [math_line(formula, note) for note, formula in rows]


def _tex(value: Any) -> str:
    from sympy import latex

    return str(latex(value))
