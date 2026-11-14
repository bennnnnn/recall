"""The real domain an equation is written on: every logarithm's argument positive, every
even root's radicand not negative.

SymPy solves over the complex numbers, where ``log(x - 5) = log(2x)`` holds at x = -5 (both
sides are log(-10)) and ``sqrt(x - 3) = sqrt(1 - x)`` at x = 2 (both are i): each came back
as a checked root of an equation with no real solution (2026-11-13 audit, MATH-02). School
algebra reads an equation over the reals, so each root is put back into the equation as it
was written (before SymPy turns ``sqrt(x)^2`` into ``x``) and a root that leaves the domain
is rejected, with the reason the working shows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sympy import N, Pow, latex, log, preorder_traversal, simplify

from app.modules.math.schemas import MathSolveResult
from app.modules.math.solve.declines import sympy_decline
from app.modules.math.solve.key_step import KeyStep
from app.modules.math.solve.parse import parse_expression
from app.services.solving import SolveServiceError

# A numeric value's imaginary part this small is a rounding of zero.
_REAL_TOLERANCE = 1e-12
# Why a root goes when the question asked for real solutions only.
_NOT_REAL = r"\text{ is not a real number}"


@dataclass(frozen=True)
class DomainRule:
    """One function of the unknown the reals restrict: its argument or radicand."""

    inside: Any
    # The index of an even root (2 for a square root), whose radicand is >= 0; 0 for a
    # logarithm, whose argument is > 0.
    root_index: int


@dataclass(frozen=True)
class RejectedRoot:
    root: str  # ``x = -5``
    why: str  # ``x - 5 = -10 < 0`` and the rule it breaks


def domain_rules(*sides: Any, variable: str) -> tuple[DomainRule, ...]:
    """Every logarithm and even root in ``sides`` whose inside holds ``variable``."""
    rules: list[DomainRule] = []
    for side in sides:
        for node in preorder_traversal(side):
            if isinstance(node, log):
                inside, index = node.args[0], 0
            elif isinstance(node, Pow) and (index := _even_root_index(node.exp)):
                inside = node.base
            else:
                continue
            with sympy_decline() as declined:
                inside = inside.doit()
            if declined or variable not in {str(s) for s in inside.free_symbols}:
                continue
            rule = DomainRule(inside=inside, root_index=index)
            if rule not in rules:
                rules.append(rule)
    return tuple(rules)


def written_domain_rules(lhs: str, rhs: str, variables: list[str]) -> tuple[DomainRule, ...]:
    """The rules of the equation as typed, read before SymPy simplifies it."""
    if len(variables) != 1:
        return ()
    try:
        sides = [
            parse_expression(side, variables, real=True, evaluate=False) for side in (lhs, rhs)
        ]
    except SolveServiceError:
        return ()
    return domain_rules(*sides, variable=variables[0])


def rejection(rules: tuple[DomainRule, ...], variable: str, value: Any) -> str | None:
    """Why ``value`` leaves the real domain (LaTeX), or None when it stays in it.

    A value the check cannot decide (it holds a parameter) stays.
    """
    for rule in rules:
        at = _value_at(rule.inside, variable, value)
        if at is None:
            continue
        inside = rf"{latex(rule.inside)} = {latex(at)}"
        real, sign = _real_sign(at)
        if real is None:
            continue
        if not real:
            return rf"{inside}\text{{, not a real number}}"
        if rule.root_index and sign < 0:
            root = "a square root" if rule.root_index == 2 else "an even root"
            return rf"{inside} < 0\text{{, and {root} needs a number}} \ge 0"
        if not rule.root_index and sign <= 0:
            relation = " < 0" if sign < 0 else ""
            return rf"{inside}{relation}\text{{, and a logarithm needs a positive number}}"
    return None


def split_by_domain(
    rules: tuple[DomainRule, ...], variable: str, values: list[Any]
) -> tuple[list[Any], list[RejectedRoot]]:
    """``values`` kept in the real domain, and each one rejected with why."""
    kept: list[Any] = []
    rejected: list[RejectedRoot] = []
    for value in values:
        why = rejection(rules, variable, value)
        if why is None:
            kept.append(value)
        else:
            rejected.append(RejectedRoot(root=f"{variable} = {latex(value)}", why=why))
    return kept, rejected


def rejected_root_steps(rejected: list[RejectedRoot]) -> list[KeyStep]:
    """One worked step per rejected root: the root checked, and why it fails."""
    return [KeyStep(label=f"Check ${item.root}$", formula=item.why) for item in rejected]


def not_real(variable: str, value: Any) -> RejectedRoot:
    """A root dropped because the question asked for real solutions only."""
    return RejectedRoot(root=f"{variable} = {latex(value)}", why=f"{latex(value)}{_NOT_REAL}")


def with_rejected_roots(key_steps: list[KeyStep], result: MathSolveResult) -> list[KeyStep]:
    """The worked steps, then a check of each root the solver rejected that the trace did
    not check itself. Non-real roots dropped for a real-only question are one step. With no
    trace at all, the roots found come first, so the checks have something to check."""
    named = {step.label for step in key_steps}
    pending = [item for item in result.rejected_roots if f"Check ${item.root}$" not in named]
    if not pending:
        return key_steps
    unreal = [item.root for item in pending if item.why.endswith(_NOT_REAL)]
    checks = [
        KeyStep(label=f"Check ${item.root}$", formula=item.why)
        for item in pending
        if not item.why.endswith(_NOT_REAL)
    ]
    if unreal:
        joined = r" \text{ or } ".join(unreal)
        checks.append(
            KeyStep(label="Keep only real roots", formula=rf"{joined}\text{{: not real numbers}}")
        )
    if key_steps:
        return [*key_steps, *checks]
    found = [*result.solutions_latex, *(item.root for item in result.rejected_roots)]
    return [KeyStep(label="Solve the equation", formula=r" \text{ or } ".join(found)), *checks]


def _even_root_index(exponent: Any) -> int:
    """2 for ``x^(1/2)`` and ``x^(3/2)``, 4 for ``x^(1/4)``; 0 for any other power."""
    with sympy_decline() as declined:
        exponent = exponent.doit()
        index = int(exponent.q) if exponent.is_Rational and exponent.q % 2 == 0 else 0
    return 0 if declined else index


def _value_at(inside: Any, variable: str, value: Any) -> Any | None:
    """``inside`` with ``value`` put in, simplified; None when a parameter is left."""
    with sympy_decline() as declined:
        at = simplify(inside.subs({s: value for s in inside.free_symbols if str(s) == variable}))
    if declined or at.free_symbols:
        return None
    return at


def _real_sign(at: Any) -> tuple[bool | None, int]:
    """(whether ``at`` is real, its sign): SymPy's own answer, else a 30-digit numeral."""
    with sympy_decline() as declined:
        real = at.is_real
        if real:
            if at.is_zero:
                return True, 0
            if at.is_positive is not None:
                return True, 1 if at.is_positive else -1
        number = complex(N(at, 30))
    if declined:
        return None, 0
    if abs(number.imag) > _REAL_TOLERANCE * max(1.0, abs(number.real)):
        return False, 0
    if abs(number.real) <= _REAL_TOLERANCE:
        return True, 0
    return True, 1 if number.real > 0 else -1
