"""Odd-index roots solved over the reals.

SymPy takes the principal complex branch of a rational power, under which the cube root of
-8 is not -2. So ``x^(2/3) = 4`` gave only 8, ``(x - 1)^(1/3) = -2`` "no solution" (x = -7),
``(3x)^(1/3) = -3`` "no solution" (x = -9: SymPy splits it into 3^(1/3)·x^(1/3)),
``x^(1/3) = x`` {0, 1} without -1, and ``x^(1/3) + x^(2/3) = 2`` {1} without -8 (2026-11-13
audit and 2026-11-14 review). In real algebra an odd root is defined for a negative radicand
too. An equation that holds an odd root of the unknown is solved here, over the reals, or
declined (``SolveServiceError``): never the complex branch's answer in its place.
"""

from __future__ import annotations

from math import lcm
from typing import Any

from sympy import Add, Dummy, Eq, Rational, S, Symbol, preorder_traversal, simplify, solve, solveset

from app.services.solving import SolveServiceError


def odd_root_equation(lhs: Any, rhs: Any, sym: Any) -> tuple[Any, Any] | None:
    """``(power, value)`` when the equation is one odd-index root of the unknown set to a
    number: ``x^(2/3) = 4``, ``(x - 1)^(1/3) = -2``, ``(x - 1)^(1/3) + 2 = 0``, ``(3x)^(1/3)
    = -3`` (a number's root beside it, 3^(1/3)·x^(1/3), divided out); else None."""
    for power, target in ((lhs, rhs), (rhs, lhs)):
        if _odd_root(power, sym) and getattr(target, "is_number", False):
            return power, target
    terms = Add.make_args(lhs - rhs)
    varying = [term for term in terms if sym in term.free_symbols]
    if len(varying) != 1:
        return None
    coefficient, power = varying[0].as_independent(sym, as_Add=False)
    rest = Add(*(term for term in terms if term is not varying[0]))
    if not _odd_root(power, sym) or coefficient == 0 or not getattr(rest, "is_number", False):
        return None
    return power, simplify(-rest / coefficient)


def real_odd_root_solutions(lhs: Any, rhs: Any, sym: Any) -> list[Any] | None:
    """The real solutions of an equation holding an odd root of the unknown; None when it
    holds none (the ordinary solver's equation)."""
    isolated = odd_root_equation(lhs, rhs, sym)
    if isolated is not None:
        return _isolated_solutions(*isolated, sym)
    expr = lhs - rhs
    roots = {node for node in preorder_traversal(expr) if _rational_root(node, sym)}
    odd = {root for root in roots if root.exp.q % 2 == 1}
    if not odd:
        return None  # even roots alone: the ordinary solve, then the real-domain check
    if len(odd) < len(roots):
        # An even root beside an odd one: neither reading here holds.
        raise SolveServiceError("odd and even roots of the unknown together")
    return _substituted_solutions(expr, odd, sym)


def _isolated_solutions(power: Any, target: Any, sym: Any) -> list[Any]:
    """``base^(p/q) = a`` with q odd is ``base^p = a^q`` over the reals."""
    if target.is_real is False:
        return []
    real_sym = Symbol(str(sym), real=True)
    base = power.base.subs(sym, real_sym)
    exponent = power.exp
    equation = Eq(base ** int(exponent.p), simplify(target ** int(exponent.q)))
    found = solveset(equation, real_sym, domain=S.Reals)
    if not getattr(found, "is_FiniteSet", False):
        raise SolveServiceError("odd-root equation with no finite real solution set")
    return list(found)


def _substituted_solutions(expr: Any, roots: set[Any], sym: Any) -> list[Any]:
    """One radicand B under every root: t, B's real root of the roots' common odd index Q,
    stands for each root (B^(p/q) is t^(pQ/q)) and B = t^Q gives the unknown back.
    ``x^(1/3) = x`` is t = t^3, so t is -1, 0 or 1, and x = t^3."""
    bases: list[Any] = []
    for root in roots:
        if not any(simplify(root.base - base) == 0 for base in bases):
            bases.append(root.base)
    if len(bases) != 1:
        raise SolveServiceError("odd roots of several radicands")
    index = lcm(*(int(root.exp.q) for root in roots))
    t = Dummy("t", real=True)
    unknown = solve(Eq(bases[0], t**index), sym)
    if len(unknown) != 1:
        raise SolveServiceError("the radicand does not give the unknown back")
    in_t = expr.xreplace({root: t ** int(root.exp * index) for root in roots})
    in_t = simplify(in_t.subs(sym, unknown[0]))
    if sym in in_t.free_symbols:
        raise SolveServiceError("the unknown is left outside the roots")
    found = solveset(in_t, t, S.Reals)
    if not getattr(found, "is_FiniteSet", False):
        raise SolveServiceError("odd-root equation with no finite real solution set")
    return [simplify(unknown[0].subs(t, value)) for value in found]


def _odd_root(power: Any, sym: Any) -> bool:
    return _rational_root(power, sym) and power.exp.q % 2 == 1 and power.exp.p > 0


def _rational_root(power: Any, sym: Any) -> bool:
    exponent = getattr(power, "exp", None)
    return bool(
        getattr(power, "is_Pow", False)
        and sym in power.base.free_symbols
        and isinstance(exponent, Rational)
        and exponent.q != 1
    )
