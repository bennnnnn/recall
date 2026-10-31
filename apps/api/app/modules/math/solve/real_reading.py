"""An expression read over the real numbers, as school algebra reads it: an odd root of a
negative number is negative (``∛(-8) = -2``), an even root of one is undefined.

``agrees_on_reals`` decides whether a rewritten form equals the expression for every real
value of its letters. A fixed set of sample points is no proof: ``√(12(x + 5)²)`` and
``2√3(x + 5)`` agree at every point above -5. Each side is one algebraic function between
the points where an absolute value's argument or a radicand changes sign, so the check
samples both sides of every such point, and far out beyond them. With several letters
that is certain only when each such argument is a single term (its sign changes only
where a letter's does), so every combination of signs is sampled; anything else is not
established and the rewrite is refused.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

from sympy import Abs, Dummy, Eq, Poly, PolynomialError, Pow, S, fraction, solve, solveset, together

_SAMPLES = (-2.37, -1.29, -0.61, 0.47, 1.73, 3.11)
_MAX_DEGREE = 12
_MAX_LETTERS = 4


def agrees_on_reals(original: Any, candidate: Any) -> bool:
    """Equal wherever the original is defined, read with real odd roots."""
    symbols = sorted(original.free_symbols | candidate.free_symbols, key=str)
    points = _sample_points([original, candidate], symbols)
    if points is None:
        return False
    compared = 0
    for point in points:
        expected = _real_value(original, point)
        if expected is None:
            continue
        got = _real_value(candidate, point)
        if got is None or not math.isclose(expected, got, rel_tol=1e-9, abs_tol=1e-9):
            return False
        compared += 1
    return compared >= 2


def _sign_arguments(expressions: list[Any]) -> list[Any]:
    """What an absolute value or a root is taken of: where its sign changes, the
    expression's formula can. |u| inside one is read as u, whose cuts are taken too."""
    found: list[Any] = []
    for expression in expressions:
        found += [node.args[0] for node in expression.atoms(Abs)]
        found += [
            node.base
            for node in expression.atoms(Pow)
            if node.exp.is_Rational and not node.exp.is_Integer
        ]
    return [
        argument.replace(lambda node: isinstance(node, Abs), lambda node: node.args[0])
        for argument in found
    ]


def _sample_points(expressions: list[Any], symbols: list[Any]) -> list[dict[Any, float]] | None:
    if not symbols:
        return [{}, {}]
    try:
        return _points_for(_sign_arguments(expressions), symbols)
    except PolynomialError:
        return None


def _points_for(arguments: list[Any], symbols: list[Any]) -> list[dict[Any, float]] | None:
    if len(symbols) == 1:
        cuts = _real_cuts(arguments, symbols[0])
        if cuts is None:
            return None
        return [{symbols[0]: value} for value in _around(cuts)]
    if len(symbols) > _MAX_LETTERS or not all(_single_term(arg, symbols) for arg in arguments):
        return None
    points = []
    for signs in itertools.product((-1, 1), repeat=len(symbols)):
        for magnitudes in ((0.61, 0.37), (1.73, 0.29)):
            start, step = magnitudes
            points.append(
                {
                    symbol: sign * (start + step * index)
                    for index, (sign, symbol) in enumerate(zip(signs, symbols, strict=True))
                }
            )
    return points


def _real_cuts(arguments: list[Any], symbol: Any) -> list[float] | None:
    """The real points where an argument changes sign; None when they cannot be found."""
    cuts: set[float] = set()
    for argument in arguments:
        if not argument.is_rational_function(symbol):
            return None
        for part in fraction(together(argument)):
            if symbol not in part.free_symbols:
                continue
            poly = Poly(part, symbol)
            if poly.degree() > _MAX_DEGREE:
                return None
            cuts.update(float(root) for root in poly.real_roots())
    return sorted(cuts)


def _around(cuts: list[float]) -> list[float]:
    """Two points between each pair of cuts, and two beyond each end, off any cut."""
    if not cuts:
        return list(_SAMPLES)
    points = [cuts[0] - 1.37, cuts[0] - 6.1, cuts[-1] + 1.29, cuts[-1] + 5.7]
    for low, high in itertools.pairwise(cuts):
        points += [low + (high - low) * 0.31, low + (high - low) * 0.73]
    return points


def _single_term(argument: Any, symbols: list[Any]) -> bool:
    if not argument.is_rational_function(*symbols):
        return False
    return all(
        not (set(symbols) & part.free_symbols) or Poly(part, *symbols).is_monomial
        for part in fraction(together(argument))
    )


def _real_value(node: Any, point: dict[Any, float]) -> float | None:
    """The value with real odd roots; None where it is undefined or not a real number."""
    try:
        value = _evaluate(node, point)
    except (ArithmeticError, ValueError, TypeError):
        return None
    return value if value is not None and math.isfinite(value) else None


def _evaluate(node: Any, point: dict[Any, float]) -> float | None:
    if node.is_Symbol:
        return point[node]
    if node.is_Pow:
        base = _evaluate(node.base, point)
        if base is None or not node.exp.is_Rational:
            return None
        p, q = int(node.exp.p), int(node.exp.q)
        if q == 1:
            return float(base**p)
        if base < 0 and q % 2 == 0:
            return None
        root = math.copysign(abs(base) ** (1 / q), base)
        return float(root**p)
    if node.is_Add or node.is_Mul:
        values = [_evaluate(arg, point) for arg in node.args]
        if any(value is None for value in values):
            return None
        return math.fsum(values) if node.is_Add else math.prod(values)  # type: ignore[arg-type]
    if isinstance(node, Abs):
        inner = _evaluate(node.args[0], point)
        return None if inner is None else abs(inner)
    if node.is_number and node.is_extended_real:
        return float(node)
    return None


def real_zeros(expression: Any, symbol: Any) -> list[Any]:
    """The real values of ``symbol`` that make ``expression`` zero, odd roots read as real.

    SymPy's principal cube root is never -1, so ``∛x + 1 = 0`` had no solution and the
    card ``∛x - 1`` lost its x ≠ -1. With every root an odd root of a power of the letter,
    ``x = t^Q`` (Q the roots' common index) turns them into powers of a real t, one t for
    each x."""
    expression = expression.doit()  # a typed 1/3 parses unevaluated, as 1·3⁻¹
    radicals = [
        node for node in expression.atoms(Pow) if node.exp.is_Rational and not node.exp.is_Integer
    ]
    powers = {node: _power_of(node.base, symbol) for node in radicals}
    if radicals and all(
        power is not None and node.exp.q % 2 == 1 for node, power in powers.items()
    ):
        index = math.lcm(*(int(node.exp.q) for node in radicals))
        t = Dummy("t", real=True)
        in_t = expression.xreplace(
            {node: t ** int(node.exp * index * powers[node]) for node in radicals}
        ).xreplace({symbol: t**index})
        found = solveset(Eq(in_t, 0), t, S.Reals)
        if getattr(found, "is_FiniteSet", False):
            return [value**index for value in found]
        return []
    return [value for value in solve(Eq(expression, 0), symbol) if value.is_real is not False]


def _power_of(base: Any, symbol: Any) -> int | None:
    """k when ``base`` is ``symbol^k`` (k a positive whole number)."""
    if base == symbol:
        return 1
    if getattr(base, "is_Pow", False) and base.base == symbol and base.exp.is_Integer:
        return int(base.exp) if base.exp > 0 else None
    return None
