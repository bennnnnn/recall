"""The form a "simplify" answer certifies: the one a school book prints.

SymPy's ``simplify`` keeps the form with the fewest operations, and on a tie or under
the principal complex branch that is not the book's: ``∛(162x⁵)/∛(3x²)`` stayed
``3∛2·∛(x⁵)/|x^(2/3)|``, ``(x-1)/(x³-1)`` was left uncancelled and ``x³ + x²`` came back
factored. Three rules, each one for every expression of its kind:

- An odd root of a real number is the real root (``∛(-8) = -2``). The radicals are
  combined as if every letter were positive, and that form is kept only when it agrees
  with the expression, read with real odd roots, at sample points on both sides of zero.
- A rational expression is in lowest terms: no factor is left common to the numerator
  and the denominator.
- A polynomial is its collected terms unless the factored form is genuinely shorter.

Length alone does not decide: ``1/x + 1/(x+1)`` as one fraction is longer, and it is the
book's answer.
"""

from __future__ import annotations

import math
from typing import Any

from sympy import (
    Abs,
    Dummy,
    Expr,
    Pow,
    cancel,
    count_ops,
    expand,
    factor,
    fraction,
    gcd,
    latex,
    simplify,
    together,
)

from app.modules.math.solve.radical_form import book_radicals_latex, has_radical

# Off the integers and off the points a textbook expression is undefined at (0, ±1, 2).
_SAMPLES = (-2.37, -1.29, -0.61, 0.47, 1.73, 3.11)


def simplest_form(parsed: Any) -> tuple[Any, str | None]:
    """SymPy's simplification in the book's form, and its LaTeX when a rule here changed it.

    The usual display pass simplifies again, which would undo the book's form, so a
    changed result carries its own LaTeX."""
    result = simplify(parsed)
    if not isinstance(parsed, Expr) or not isinstance(result, Expr):
        return result, None
    chosen = _real_root_form(parsed, result)
    chosen = _lowest_terms(chosen)
    chosen = _collected_polynomial(parsed, chosen)
    radicals = book_radicals_latex(chosen) if has_radical(parsed) else None
    if radicals is not None:
        return chosen, radicals
    return chosen, (None if chosen == result else latex(chosen))


def _real_odd_roots(expr: Any) -> Any:
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


def _real_root_form(parsed: Expr, result: Expr) -> Expr:
    if not has_radical(parsed):
        return result
    symbols = sorted(parsed.free_symbols, key=str)
    positive = {symbol: Dummy(str(symbol), positive=True) for symbol in symbols}
    back = {dummy: symbol for symbol, dummy in positive.items()}
    candidate = simplify(_real_odd_roots(parsed).subs(positive)).subs(back)
    if count_ops(candidate) > count_ops(result) or candidate == result:
        return result
    return candidate if _agrees(parsed, candidate, symbols) else result


def _agrees(original: Expr, candidate: Expr, symbols: list[Any]) -> bool:
    """Equal wherever the original is defined, read with real odd roots."""
    compared = 0
    for index in range(len(_SAMPLES)):
        point = {
            symbol: _SAMPLES[(index + offset) % len(_SAMPLES)] + 0.11 * offset
            for offset, symbol in enumerate(symbols)
        }
        expected = _real_value(original, point)
        if expected is None:
            continue
        got = _real_value(candidate, point)
        if got is None or not math.isclose(expected, got, rel_tol=1e-9, abs_tol=1e-9):
            return False
        compared += 1
    return compared >= 2


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


def _lowest_terms(expr: Expr) -> Expr:
    symbols = sorted(expr.free_symbols, key=str)
    if not symbols or not expr.is_rational_function(*symbols):
        return expr
    numerator, denominator = fraction(together(expr))
    if not (gcd(numerator, denominator).free_symbols & set(symbols)):
        return expr
    lowest = cancel(expr)
    return min((factor(lowest), lowest), key=count_ops)


def _collected_polynomial(parsed: Expr, chosen: Expr) -> Expr:
    symbols = sorted(parsed.free_symbols, key=str)
    if not symbols or not parsed.is_polynomial(*symbols):
        return chosen
    collected = expand(parsed)
    return collected if count_ops(collected) <= count_ops(chosen) else chosen
