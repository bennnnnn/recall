"""How big a polynomial is, read off its tree without expanding it.

Expanding ``(x+1)^3000`` to read its degree took 1.6 s of a pool worker, and factoring
``(x+1)^300 - 1`` ran past the solve's deadline (audit, 2026-11-25). These bounds are
read from the expression as written, in time linear in its size, so a guard can refuse a
problem before SymPy expands it.
"""

from __future__ import annotations

from typing import Any

from sympy import Add, Integer, Mul, Pow, Symbol

# An expansion larger than this is refused before it is written out: a school
# polynomial has a few dozen terms, ``(a+b+c)^10`` has 66.
MAX_EXPANDED_TERMS = 1000
# Factoring is the costly step: ``(x+1)^100 - 1`` factors in 0.1 s, ``(x+1)^300 - 1``
# runs past the 5 s deadline. A school polynomial is of degree 10 or so.
MAX_FACTOR_DEGREE = 100
# Above this many terms written out, a count stops at the cap.
_HUGE = MAX_EXPANDED_TERMS * 1000


def degree_bound(expr: Any, symbol: Symbol) -> int | None:
    """An upper bound on ``expr``'s degree in ``symbol`` as ``Poly`` reads it, or None when
    the tree is no polynomial in it as written (a power with a symbolic or negative exponent
    of something holding it, a function of it). Exact unless terms cancel."""
    if expr == symbol:
        return 1
    if not expr.has(symbol):
        return 0
    if isinstance(expr, Add):
        bounds = [degree_bound(arg, symbol) for arg in expr.args]
        return None if any(b is None for b in bounds) else max(b for b in bounds if b is not None)
    if isinstance(expr, Mul):
        total = 0
        for arg in expr.args:
            bound = degree_bound(arg, symbol)
            if bound is None:
                return None
            total += bound
        return total
    if isinstance(expr, Pow) and isinstance(expr.exp, Integer) and int(expr.exp) >= 0:
        base = degree_bound(expr.base, symbol)
        return None if base is None else base * int(expr.exp)
    return None


def total_degree_bound(expr: Any) -> int | None:
    """An upper bound on ``expr``'s total degree in all its symbols, or None (as above)."""
    symbols = sorted(expr.free_symbols, key=str)
    if not symbols:
        return 0
    bounds = [degree_bound(expr, symbol) for symbol in symbols]
    if any(bound is None for bound in bounds):
        return None
    # Total degree is at most the sum of the degrees in each symbol.
    return sum(bound for bound in bounds if bound is not None)


def expanded_terms(expr: Any) -> int:
    """An upper bound on how many terms ``expand`` writes for ``expr`` (before like terms
    are collected), capped far above ``MAX_EXPANDED_TERMS``."""
    if isinstance(expr, Add):
        return min(_HUGE, sum(expanded_terms(arg) for arg in expr.args))
    if isinstance(expr, Mul):
        total = 1
        for arg in expr.args:
            total = min(_HUGE, total * expanded_terms(arg))
        return total
    if isinstance(expr, Pow) and isinstance(expr.exp, Integer) and int(expr.exp) >= 0:
        terms = expanded_terms(expr.base)
        power = int(expr.exp)
        if terms <= 1:
            return 1
        # The monomials of a k-term sum raised to n: C(n + k - 1, k - 1).
        return _capped_choose(power, terms - 1)
    if expr.args:
        # A function of a sum expands inside it: count what its arguments write.
        return min(_HUGE, max(expanded_terms(arg) for arg in expr.args))
    return 1


def add_nodes(expr: Any) -> list[Any]:
    """Every sum in ``expr``'s tree: what ``factor`` expands and factors, one by one."""
    found = [expr] if isinstance(expr, Add) else []
    for arg in expr.args:
        found.extend(add_nodes(arg))
    return found


def _capped_choose(n: int, k: int) -> int:
    """C(n + k, k), stopping at ``_HUGE``: C(n + j, j) grows with j, so a large one stops
    after a few steps instead of computing a number with thousands of digits."""
    n, k = max(n, k), min(n, k)
    value = 1
    for j in range(1, k + 1):
        value = value * (n + j) // j
        if value >= _HUGE:
            return _HUGE
    return value
