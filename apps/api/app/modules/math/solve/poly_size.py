"""How big a polynomial is, read off its tree without expanding it.

Expanding ``(x+1)^3000`` to read its degree took 1.6 s of a pool worker, and factoring
``(x+1)^300 - 1`` ran past the solve's deadline (audit, 2026-11-25). These bounds are
read from the expression as written, in time linear in its size, so a guard can refuse a
problem before SymPy expands it.
"""

from __future__ import annotations

from typing import Any

from sympy import Add, Integer, Mul, Pow, Rational, Symbol

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


def size_degree(expr: Any) -> int | None:
    """An upper bound on ``expr``'s total degree as SymPy writes it out, counting a power by
    the size of its exponent: ``1/(x+1)^300`` puts a degree-300 polynomial in the
    denominator, and ``(x+1)^(3001/2)`` one of degree 1500 before its root. None for a
    function or a symbolic exponent."""
    if not expr.free_symbols:
        return 0
    if isinstance(expr, Symbol):
        return 1
    if isinstance(expr, Add | Mul):
        sizes = [size_degree(arg) for arg in expr.args]
        if any(size is None for size in sizes):
            return None
        known = [size for size in sizes if size is not None]
        return max(known) if isinstance(expr, Add) else sum(known)
    if isinstance(expr, Pow) and (power := _power(expr.exp)) is not None:
        base = size_degree(expr.base)
        return None if base is None else base * power
    return None


def expansion_size(expr: Any) -> int:
    """An upper bound on how many terms ``expand`` writes for ``expr``: the products it
    multiplies out (``expanded_terms``), and no more than a polynomial of its degree in its
    symbols has, C(d + k, k): ``(x+1)(x+2)…(x+10)`` multiplies 2^10 products into 11 terms."""
    terms = expanded_terms(expr)
    degree = size_degree(expr)
    if degree is None:
        return terms
    return min(terms, _capped_choose(degree, len(expr.free_symbols)))


def expanded_terms(expr: Any) -> int:
    """An upper bound on how many products ``expand`` multiplies out for ``expr`` (before
    like terms are collected), capped far above ``MAX_EXPANDED_TERMS``. A power is sized by
    its exponent's whole part, whatever its sign: ``(x+1)^(-9999)`` writes out a
    denominator of 10000 terms."""
    if isinstance(expr, Add):
        return min(_HUGE, sum(expanded_terms(arg) for arg in expr.args))
    if isinstance(expr, Mul):
        total = 1
        for arg in expr.args:
            total = min(_HUGE, total * expanded_terms(arg))
        return total
    if isinstance(expr, Pow) and (power := _power(expr.exp)) is not None:
        terms = expanded_terms(expr.base)
        if terms <= 1:
            return 1
        # The monomials of a k-term sum raised to n: C(n + k - 1, k - 1).
        return _capped_choose(power, terms - 1)
    if expr.args:
        # A function of a sum expands inside it: count what its arguments write.
        return min(_HUGE, max(expanded_terms(arg) for arg in expr.args))
    return 1


def _power(exponent: Any) -> int | None:
    """The whole part of a numeric exponent's size (-3000 and 3001/2 are 3000 and 1500), or
    None for a symbolic one."""
    if not isinstance(exponent, Rational):
        return None
    return min(_HUGE, int(abs(exponent)))


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
