"""The antiderivative a school answer shows: the textbook form, checked by differentiating it.

SymPy's ``integrate`` is right but often not what a student can read on a card:
``∫ (x + 2)√(x - 3) dx`` comes back as a ``Piecewise`` over complex branches with ``i`` in it,
``∫ (2x + 1)⁵ dx`` as a degree-6 polynomial over 3. The rule-based ``manualintegrate`` works
the way a textbook does (substitution, parts, the table) and gives ``(2/5)(x - 3)^{5/2} +
(10/3)(x - 3)^{3/2}`` and ``(2x + 1)⁶/12``. Its answer counts only when it is one closed
formula that differentiates back to the integrand. It is shown when ``integrate``'s is no
readable formula, or when it is no longer than that one (``count_ops``, a tie to the
textbook): ``∫ x³/(x² + 1)² dx`` keeps ``integrate``'s ``ln(x² + 1)``, not ``ln(2x⁴ + 4x² + 2)``.
A fraction of polynomials with the variable below the line never asks it: ``integrate`` already
gives the partial fractions a textbook writes, and the rule-based search can take seconds on one
(``x⁵/(x² + 1)³``: 4.7 s against 0.01 s), past the solve's time limit.

``readable_antiderivative`` says whether an antiderivative may be shown as a checked card at
all: one still holding an ``Integral``, or an ``i`` the integrand never had (a branch for the
values where a root of a real integrand is imaginary), is no answer a school student can use,
so the card is withheld and the reply works it instead. A ``Piecewise`` over a parameter
(``xⁿ⁺¹/(n + 1)`` for ``n ≠ -1``, else ``ln x``) is the whole answer and stays.
"""

from __future__ import annotations

from typing import Any

from sympy import (
    I,
    Integral,
    Piecewise,
    Rational,
    count_ops,
    diff,
    fraction,
    integrate,
    simplify,
    together,
)

from app.modules.math.solve.declines import sympy_decline

# Real points the derivative check samples; an integrand undefined or complex at one is
# skipped there (√(x - 3) is checked only at 4.3 and beyond).
_SAMPLE_POINTS = tuple(
    Rational(n, 100) for n in (37, 170, 290, 430, 560, 710, 940, 1250, -80, -230, -470)
)
_CHECKED_POINTS = 3
_TOLERANCE = 1e-9


def textbook_antiderivative(integrand: Any, sym: Any) -> Any:
    """``∫ integrand d(sym)`` without ``+ C``: the textbook form when it checks and reads no
    worse, else SymPy's."""
    from sympy.integrals.manualintegrate import manualintegrate

    found = integrate(integrand, sym)
    if _partial_fractions(integrand, sym):
        return found
    with sympy_decline() as declined:
        worked = manualintegrate(integrand, sym)
    if declined or not _finished(worked) or not readable_antiderivative(worked, integrand):
        return found
    if not differentiates_to(worked, integrand, sym):
        return found
    if not _finished(found) or not readable_antiderivative(found, integrand):
        return worked
    return worked if count_ops(worked) <= count_ops(found) else found


def readable_antiderivative(result: Any, integrand: Any) -> bool:
    """Whether a school card may show this antiderivative: closed, and real where ``f`` is."""
    if result.has(Integral):
        return False
    return not (result.has(I) and not integrand.has(I))


def _partial_fractions(integrand: Any, sym: Any) -> bool:
    """A fraction of polynomials in ``sym`` with ``sym`` in its denominator."""
    if not integrand.is_rational_function(sym):
        return False
    _numerator, denominator = fraction(together(integrand))
    return bool(denominator.has(sym))


def _finished(result: Any) -> bool:
    """A rule-based answer worth preferring: closed, and one formula (its ``Piecewise`` can
    carry a wrong domain, ``√(x² - 1)/x`` on ``-1 < x < 1``)."""
    return not result.has(Integral) and not result.has(Piecewise)


def differentiates_to(candidate: Any, integrand: Any, sym: Any) -> bool:
    """``d/dx F = f`` at a few real points where ``f`` is real, or symbolically without them."""
    gap = diff(candidate, sym) - integrand
    checked = 0
    for point in _SAMPLE_POINTS:
        with sympy_decline() as declined:
            want = complex(integrand.subs(sym, point).evalf())
            miss = complex(gap.subs(sym, point).evalf())
        if declined or want.imag != 0 or not _finite(want) or not _finite(miss):
            continue
        if abs(miss) > _TOLERANCE * (1 + abs(want)):
            return False
        checked += 1
    if checked >= _CHECKED_POINTS:
        return True
    with sympy_decline() as declined:
        exact = simplify(gap) == 0
    return exact and not declined


def _finite(value: complex) -> bool:
    return all(abs(part) != float("inf") and part == part for part in (value.real, value.imag))
