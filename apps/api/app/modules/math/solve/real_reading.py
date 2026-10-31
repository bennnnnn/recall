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
import logging
import math
from typing import Any

from sympy import (
    Abs,
    Dummy,
    Eq,
    Poly,
    Pow,
    S,
    expand,
    fraction,
    resultant,
    solve,
    solveset,
    together,
)

logger = logging.getLogger(__name__)

_SAMPLES = (-2.37, -1.29, -0.61, 0.47, 1.73, 3.11)
# Past these the check is not worth its time; SymPy's own form stands.
_MAX_DEGREE = 6
_MAX_ARGUMENTS = 8
_MAX_LETTERS = 4


def agrees_on_reals(original: Any, candidate: Any) -> bool:
    """Equal wherever the original is defined, read with real odd roots. Anything this
    cannot establish (a sign it cannot place, a check past its bounds) is a no."""
    try:
        return _agrees(original, candidate)
    except Exception as exc:
        logger.info("real reading not established (%s); keeping SymPy's form", type(exc).__name__)
        return False


def _agrees(original: Any, candidate: Any) -> bool:
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
    arguments = _sign_arguments(expressions)
    if len(arguments) > _MAX_ARGUMENTS:
        return None
    return _points_for(arguments, symbols)


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
            poly = Poly(part, symbol).sqf_part()  # x⁹ changes sign where x does
            if poly.degree() > _MAX_DEGREE:
                return None
            cuts.update(_real_roots(poly))
    return sorted(cuts)


def _real_roots(poly: Any) -> list[float]:
    """Exactly for rational coefficients; numerically for √2 or π ones, which exact real
    roots refuse (a cut only has to fall between the sample points). Repeated roots go
    first: the numeric search does not converge on x³."""
    if poly.domain.is_QQ or poly.domain.is_ZZ:
        return [float(root) for root in poly.real_roots()]
    roots = (complex(root) for root in poly.sqf_part().nroots(maxsteps=200))
    return [root.real for root in roots if abs(root.imag) < 1e-7]


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


def real_odd_roots(expr: Any) -> Any:
    """``(-8x⁶)^(1/3)`` as ``-(8x⁶)^(1/3)``: an odd root keeps the radicand's sign."""
    return expr.replace(
        lambda node: (
            node.is_Pow
            and node.exp.is_Rational
            and not node.exp.is_Integer
            and node.exp.q % 2 == 1
            and node.base.could_extract_minus_sign()
        ),
        lambda node: (-1) ** node.exp.p * Pow(-node.base, node.exp),
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
        known = [value for value in values if value is not None]
        if len(known) != len(values):
            return None
        return math.fsum(known) if node.is_Add else math.prod(known)
    if isinstance(node, Abs):
        inner = _evaluate(node.args[0], point)
        return None if inner is None else abs(inner)
    if node.is_number and node.is_extended_real:
        return float(node)
    return None


def real_zeros(expression: Any, symbol: Any) -> list[Any] | None:
    """The real values of ``symbol`` that make ``expression`` zero, odd roots read as real;
    None when they cannot be established.

    SymPy's principal cube root is never negative, so ``∛x + 1 = 0`` and ``∛(x-1) + 2 = 0``
    had no solution and their cards lost x ≠ -1 and x ≠ -7. Each odd root ∛b becomes a
    real t with t³ = b, the t's are eliminated (resultants), and every candidate the
    polynomial left in x gives is kept only if the expression is zero there."""
    expression = expression.doit()  # a typed 1/3 parses unevaluated, as 1·3⁻¹
    radicals = [
        node for node in expression.atoms(Pow) if node.exp.is_Rational and not node.exp.is_Integer
    ]
    if not radicals or any(node.exp.q % 2 == 0 for node in radicals):
        # No root, or an even one: where it is defined the principal root is the real one.
        return [value for value in solve(Eq(expression, 0), symbol) if value.is_real is not False]
    try:
        return _odd_root_zeros(expression, symbol, radicals)
    except Exception as exc:  # not established is not "no zeros"
        logger.info("real zeros not established (%s)", type(exc).__name__)
        return None


def _odd_root_zeros(expression: Any, symbol: Any, radicals: list[Any]) -> list[Any] | None:
    if any(node.base.atoms(Pow) & set(radicals) for node in radicals):
        return None  # a root inside a root
    letters: dict[tuple[Any, int], Any] = {}
    for node in radicals:
        letters.setdefault((node.base, int(node.exp.q)), Dummy("t", real=True))
    if len(letters) > 3:
        return None
    rational = expression.xreplace(
        {node: letters[(node.base, int(node.exp.q))] ** int(node.exp.p) for node in radicals}
    )
    polynomial = expand(fraction(together(rational))[0])
    for (base, index), letter in letters.items():
        top, bottom = fraction(together(base))
        polynomial = resultant(polynomial, letter**index * bottom - top, letter)
    if polynomial.free_symbols - {symbol} or Poly(polynomial, symbol).degree() > _MAX_DEGREE:
        return None
    candidates = solveset(Eq(polynomial, 0), symbol, S.Reals)
    if not getattr(candidates, "is_FiniteSet", False):
        return None
    return [
        value
        for value in candidates
        if (found := _real_value(expression, {symbol: float(value)})) is not None
        and abs(found) < 1e-9
    ]
