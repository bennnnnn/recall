"""Verified traces for logarithm equations: same-base logarithms summed to a number, and one
logarithm equal to another of the same base.

Each candidate root is put back into every logarithm, and one whose argument is not positive
is rejected with that reason (``real_domain``). ``log(x - 5) = log(2x)`` gives x = -5, where
both arguments are negative: its trace ends at that check, for the answer "no real
solution", where it was once a checked x = -5 (2026-11-13 audit, MATH-02).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sympy import E, Eq, latex, log, prod, simplify, solve

from app.modules.math.solve.declines import sympy_decline
from app.modules.math.solve.key_step import KeyStep, canonical_root_formula, equation_tex
from app.modules.math.solve.real_domain import (
    domain_rules,
    rejected_root_steps,
    split_by_domain,
)
from app.modules.math.solve.root_latex import expr_equal


def _logarithm(term: Any) -> tuple[Any, Any] | None:
    """``(base, argument)`` of one logarithm: ``ln u`` or the parser's ``log(u)/log(b)``."""
    if not hasattr(term, "as_numer_denom"):
        return None  # a plain number side: ``x = 5`` passed as ints
    numerator, denominator = term.as_numer_denom()
    if getattr(numerator, "func", None) is not log:
        return None
    if denominator == 1:
        return E, numerator.args[0]
    if getattr(denominator, "func", None) is log and len(denominator.args) == 1:
        return denominator.args[0], numerator.args[0]
    return None


def _log_tex(base: Any) -> str:
    return r"\ln" if base == E else rf"\log_{{{latex(base)}}}"


def _domain_line(arguments: list[Any]) -> str:
    return r" \text{ and } ".join(rf"{latex(argument)} > 0" for argument in arguments)


def _checked(
    steps: list[KeyStep], lhs: Any, rhs: Any, var: Any, candidates: list[Any]
) -> list[KeyStep]:
    """``steps`` closed by a check of each root a logarithm rules out, then the roots kept.

    Every root rejected leaves the trace at its checks: the answer says no real solution.
    """
    kept, rejected = split_by_domain(
        domain_rules(lhs, rhs, variable=str(var)), str(var), candidates
    )
    closing = [*steps, *rejected_root_steps(rejected)]
    if kept:
        closing.append(
            KeyStep(
                label="Reject values outside the domain",
                formula=canonical_root_formula(var, kept),
            )
        )
    return closing


# The dispatcher's own working of the equation a log trace reaches (``worked_steps``),
# passed in so this module stays below it.
Worked = Callable[..., list[KeyStep]]


def logarithm_key_steps(lhs: Any, rhs: Any, var: Any, worked: Worked) -> list[KeyStep] | None:
    """Verified trace for a sum of same-base logarithms equal to a number."""
    if var in getattr(rhs, "free_symbols", set()):
        return None
    terms = lhs.args if getattr(lhs, "is_Add", False) else (lhs,)
    arguments: list[Any] = []
    base: Any | None = None
    for term in terms:
        read = _logarithm(term)
        if read is None or (base is not None and not expr_equal(base, read[0])):
            return None
        base = read[0]
        arguments.append(read[1])
    if base is None or not arguments:
        return None
    with sympy_decline() as declined:
        combined = prod(arguments)
        target = simplify(base**rhs)
        candidates = solve(Eq(combined, target), var)
    if declined or not candidates:
        return []
    combine: list[KeyStep] = []
    if len(arguments) > 1:  # one logarithm has nothing to combine
        combine.append(
            KeyStep(
                label="Combine logarithms",
                formula=rf"{_log_tex(base)}\left({latex(combined)}\right) = {latex(rhs)}",
            )
        )
    steps = [
        KeyStep(label="Domain restriction", formula=_domain_line(arguments)),
        *combine,
        KeyStep(
            label="Convert to exponential form",
            formula=rf"{latex(combined)} = {latex(target)}",
        ),
        *worked(
            combined,
            target,
            var,
            "Solve the resulting equation",
            canonical_root_formula(var, candidates),
        ),
    ]
    return _checked(steps, lhs, rhs, var, candidates)


def equal_logarithms_key_steps(
    lhs: Any, rhs: Any, var: Any, worked: Worked
) -> list[KeyStep] | None:
    """``log_b(A) = log_b(B)``: the arguments are equal, and both must be positive."""
    left, right = _logarithm(lhs), _logarithm(rhs)
    if left is None or right is None or not expr_equal(left[0], right[0]):
        return None
    first, second = left[1], right[1]
    if var not in first.free_symbols | second.free_symbols:
        return None
    with sympy_decline() as declined:
        candidates = solve(Eq(first, second), var)
    if declined or not candidates:
        return []
    steps = [
        KeyStep(label="Domain restriction", formula=_domain_line([first, second])),
        KeyStep(label="Equal logarithms, so equal arguments", formula=equation_tex(first, second)),
        *worked(
            first,
            second,
            var,
            "Solve the resulting equation",
            canonical_root_formula(var, candidates),
        ),
    ]
    return _checked(steps, lhs, rhs, var, candidates)


def logarithm_trace(lhs: Any, rhs: Any, var: Any, worked: Worked) -> list[KeyStep] | None:
    """Either logarithm trace, or None when the equation is neither shape."""
    steps = logarithm_key_steps(lhs, rhs, var, worked)
    return steps if steps is not None else equal_logarithms_key_steps(lhs, rhs, var, worked)
