"""The working of a trig equation in an interval: one side zero, an identity, factor, each factor.

``sin(2x) = cos(x)`` for ``0 <= x < 2pi``:

    sin 2x - cos x = 0                 move every term to one side
    2 sin x cos x - cos x = 0          sin 2x = 2 sin x cos x
    cos x (2 sin x - 1) = 0            factor
    cos x = 0  =>  x = pi/2, 3pi/2
    2 sin x - 1 = 0  =>  sin x = 1/2  =>  x = pi/6, 5pi/6

Every line is SymPy's: each rewrite is checked equal to the line before it, each
factor's solutions are ``solveset``'s in the interval, and the factors' solutions
together must be the equation's. Anything unchecked leaves the working out (None).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.modules.math.solve.declines import sympy_decline
from app.services.workout import math_line

# Solutions in the interval as the answer shows them, with their relation:
# ``= \frac{\pi}{6},\;\frac{5\pi}{6}`` or ``\approx 17.46^\circ``.
ValuesText = Callable[[list[Any]], str]


def _trig_atoms(expr: Any, variable: Any) -> set[Any]:
    from sympy import cos, cot, csc, sec, sin, tan

    return {atom for atom in expr.atoms(sin, cos, tan, cot, sec, csc) if atom.has(variable)}


def _one_function_forms(expr: Any, variable: Any) -> list[Any]:
    """``expr`` with ``cos^2 u`` written as ``1 - sin^2 u`` (and back), so one function is left."""
    from sympy import cos, expand, sin

    arguments = {atom.args[0] for atom in _trig_atoms(expr, variable)}
    if len(arguments) != 1:
        return []
    (u,) = arguments
    return [
        expand(expr.subs(cos(u) ** 2, 1 - sin(u) ** 2)),
        expand(expr.subs(sin(u) ** 2, 1 - cos(u) ** 2)),
    ]


def _solvable_factors(expr: Any, variable: Any) -> list[Any] | None:
    """The factors of ``expr`` holding the variable, when each is in one trig function."""
    from sympy import factor_list

    _, factors = factor_list(expr)
    kept = [part for part, _power in factors if part.has(variable)]
    if not kept or any(len(_trig_atoms(part, variable)) != 1 for part in kept):
        return None
    return kept


def _identity_note(original: Any, rewritten: Any, variable: Any) -> str:
    """The identities the rewrite used: each function it took out, as it now reads."""
    from sympy import cos, expand_trig, latex, sin

    kept = _trig_atoms(rewritten, variable)
    shown: list[str] = []
    for atom in sorted(_trig_atoms(original, variable) - kept, key=str):
        expanded = expand_trig(atom)
        if expanded == atom:
            # A square went: cos^2 u = 1 - sin^2 u.
            u = atom.args[0]
            other = sin(u) if atom.func == cos else cos(u)
            shown.append(f"${latex(atom**2)} = {latex(1 - other**2)}$")
            continue
        forms = (expanded, *_one_function_forms(expanded, variable))
        form = next((form for form in forms if _trig_atoms(form, variable) <= kept), expanded)
        shown.append(f"${latex(atom)} = {latex(form)}$")
    return "use " + ", ".join(shown) if shown else "use $\\sin^2 u + \\cos^2 u = 1$"


def _rewrite(zeroed: Any, variable: Any) -> tuple[Any, list[Any]] | None:
    """An identity form of ``zeroed`` whose factors are each in one trig function."""
    from sympy import expand_trig, simplify

    expanded = expand_trig(zeroed)
    for form in (zeroed, expanded, *_one_function_forms(expanded, variable)):
        factors = _solvable_factors(form, variable)
        if factors is not None and simplify(form - zeroed) == 0:
            return form, factors
    return None


def solutions_in(
    expr: Any, variable: Any, domain: Any, *, empty_allowed: bool = False
) -> Any | None:
    """The checked solutions of ``expr = 0`` in the interval ``domain``, or None.

    The interval solve must finish with a finite set, or there is no answer: an
    interval of solutions, a set SymPy cannot finish, or a solve that raised (``Max``,
    ``sign``) is None, never "no solution". SymPy's interval solve also drops roots of a
    quadratic in one function (``2 sin^2 x - sin x - 1`` on ``[0, 2pi)`` gives ``pi/2``
    alone, though its real solve has ``7pi/6`` and ``11pi/6``), so the real solve's
    roots in the interval are added. Each root must give 0 when substituted; an
    interval root that does not is None. No root at all is no solution (an empty set)
    when both solves finished empty (``sin x = 2``), and None when the real solve did
    not finish; ``empty_allowed`` (one factor of an equation already solved) takes a
    finished empty interval solve as no root.
    """
    from sympy import FiniteSet, N, S, simplify, solveset

    with sympy_decline() as declined:
        in_domain = solveset(expr, variable, domain=domain)
    if declined:
        return None
    if in_domain == S.EmptySet:
        in_domain = FiniteSet()
    elif not isinstance(in_domain, FiniteSet):
        return None
    extra: list[Any] = []
    real_finished = False
    with sympy_decline() as declined:  # the real solve only adds roots
        over_reals = solveset(expr, variable, domain=S.Reals).intersect(domain)
        real_finished = over_reals == S.EmptySet or isinstance(over_reals, FiniteSet)
        if isinstance(over_reals, FiniteSet):
            known = list(in_domain)
            extra = [value for value in over_reals if value not in known]

    def holds(value: Any) -> bool:
        with sympy_decline():
            if domain.contains(value) is not S.true:
                return False
            rest = simplify(expr.subs(variable, value))
            return bool(rest == 0 or abs(complex(N(rest, 30))) < 1e-20)
        return False  # the check itself failed: not shown to hold

    if not all(holds(value) for value in in_domain):
        return None
    kept = [*in_domain, *(value for value in extra if holds(value))]
    return FiniteSet(*kept) if kept or empty_allowed or real_finished else None


@dataclass(frozen=True)
class SolveRange:
    """What every line is solved over, and how its solutions read."""

    variable: Any
    domain: Any
    values_text: ValuesText
    degrees: bool


def _end_text(value: Any, degrees: bool) -> str:
    from sympy import latex, pi, simplify

    return f"{latex(simplify(value * 180 / pi))}^\\circ" if degrees else str(latex(value))


def _angle_line(atom: Any, factor: Any, over: SolveRange, ordered: list[Any]) -> str | None:
    """``2x = \\frac{\\pi}{3}, …`` over the angle's own interval, which gives each ``x``.

    ``cos 2x = 1/2`` for ``0 <= x < 2pi`` is ``cos u = 1/2`` for ``0 <= u < 4pi``; its
    angles, solved apart, must be exactly ``2x`` at the solutions, or the line is left out.
    """
    from sympy import Dummy, FiniteSet, diff, expand, latex
    from sympy import Interval as Span

    angle, domain = atom.args[0], over.domain
    slope = diff(angle, over.variable)
    offset = expand(angle - slope * over.variable)
    if slope.has(over.variable) or offset.has(over.variable) or slope == 0:
        return None  # sin(x^2): no angle a line maps the interval onto
    flipped = bool(slope < 0)
    low, high = sorted([slope * domain.start + offset, slope * domain.end + offset], key=float)
    left_open = domain.right_open if flipped else domain.left_open
    right_open = domain.left_open if flipped else domain.right_open
    u = Dummy("u", real=True)
    angles = solutions_in(
        factor.subs(angle, u), u, Span(low, high, left_open=left_open, right_open=right_open)
    )
    if angles is None or angles != FiniteSet(*(slope * value + offset for value in ordered)):
        return None
    shown = latex(angle)
    left, right = ("<" if left_open else r"\le"), ("<" if right_open else r"\le")
    span = f"{_end_text(low, over.degrees)} {left} {shown} {right} {_end_text(high, over.degrees)}"
    return f"{shown} {over.values_text(sorted(angles, key=float))} \\quad ({span})"


def _factor_line(
    factor: Any, over: SolveRange, head: str, note: str | None = None
) -> tuple[str, Any] | None:
    """``2 sin x - 1 = 0 => sin x = 1/2 => x = ...`` and the factor's solutions."""
    from sympy import Dummy, latex, solve

    variable = over.variable
    (atom,) = _trig_atoms(factor, variable)
    stand_in = Dummy("t")
    values = solve(factor.subs(atom, stand_in), stand_in)
    if not values or any(value.has(variable) for value in values):
        return None
    found = solutions_in(factor, variable, over.domain, empty_allowed=True)
    if found is None:
        return None
    chain = [head]
    isolated = r" \text{ or } ".join(f"{latex(atom)} = {latex(value)}" for value in values)
    if factor != atom and isolated != head:
        chain.append(isolated)  # "cos x = 0" and "cos 2x = 1/2" already say it
    ordered = sorted(found, key=lambda value: float(value))
    if ordered and atom.args[0] != variable:
        angles = _angle_line(atom, factor, over, ordered)
        if angles is None:
            return None
        chain.append(angles)
    chain.append(
        f"{latex(variable)} {over.values_text(ordered)}" if ordered else r"\text{no solution here}"
    )
    if not ordered:
        note = "outside the interval or the function's range"
    return math_line(r" \Rightarrow ".join(chain), note), found


def identity_factor_steps(
    lhs: Any, rhs: Any, over: SolveRange, solved: Any
) -> tuple[str, ...] | None:
    """The working from ``lhs = rhs`` to its solutions ``solved`` in the interval, or None.

    One factor and no identity (``3 sin x = 1``) is one line from the equation as
    given; ``sin x = 1/2`` has nothing to work and is None.
    """
    from sympy import Union, factor, latex, simplify

    variable = over.variable
    zeroed = lhs - rhs
    atoms = _trig_atoms(zeroed, variable)
    if not atoms or (lhs in atoms and lhs.args[0] == variable and not rhs.has(variable)):
        return None
    rewritten = _rewrite(zeroed, variable)
    if rewritten is None:
        return None
    form, factors = rewritten
    steps: list[str] = []
    heads: list[tuple[str, str | None]]
    identity = _identity_note(zeroed, form, variable) if form != zeroed else None
    if identity and rhs != 0:
        steps.append(math_line(f"{latex(zeroed)} = 0", "move every term to one side"))
    if len(factors) > 1:
        if identity:
            steps.append(math_line(f"{latex(form)} = 0", identity))
        factored = factor(form)
        if simplify(factored - form) != 0:
            return None
        steps.append(math_line(f"{latex(factored)} = 0", "factor"))
        heads = [(f"{latex(part)} = 0", None) for part in factors]
    else:
        # One factor: one line, from the identity form or from the question as given.
        factors = [form]
        heads = [
            (f"{latex(form)} = 0", identity) if identity else (f"{latex(lhs)} = {latex(rhs)}", None)
        ]
    found: list[Any] = []
    for part, (head, note) in zip(factors, heads, strict=True):
        line = _factor_line(part, over, head, note)
        if line is None:
            return None
        steps.append(line[0])
        found.append(line[1])
    if Union(*found) != solved:
        return None
    return tuple(steps)
