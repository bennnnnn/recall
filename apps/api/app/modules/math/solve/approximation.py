"""Numerical methods a question names, worked as it asks: a rule of integration with n
subintervals, Newton's method for n steps, Euler's method with step h.

Every value is SymPy's exact number, so the working and the card agree to the digit: the
trapezoidal rule with n = 4 on x^2 over [0, 2] is 11/4 = 2.75, not the integral 8/3, and one
Newton step on x^2 - 5 from 3 is 7/3, not √5 (2026-11-13 audit, MATH-01).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sympy import Integer, Rational, Symbol, diff, latex, nsimplify, simplify

from app.modules.math.solve.parse import parse_expression
from app.services.solving import SolveServiceError

# Past these a worked list stops being a page a student reads.
MAX_SUBINTERVALS = 50
MAX_STEPS = 10
_SIGNIFICANT = 6


@dataclass(frozen=True)
class RuleSum:
    rule: str
    h: Any
    nodes: tuple[Any, ...]
    weights: tuple[Any, ...]
    values: tuple[Any, ...]
    # The factor before the bracket: h/2 (trapezoid), h/3 (Simpson), h (the others).
    factor: Any
    total: Any


def exact_number(text: str) -> Any:
    """A bound or a start as the exact number it writes (``0.5`` is 1/2)."""
    value = parse_expression(text, [])
    if getattr(value, "free_symbols", None):
        raise SolveServiceError("not a number")
    return nsimplify(value, rational=True) if value.is_Float else value


def rule_sum(expr_text: str, variable: str, low: str, high: str, n: int, rule: str) -> RuleSum:
    """``rule`` with ``n`` equal subintervals on [low, high]."""
    if not 1 <= n <= MAX_SUBINTERVALS or (rule == "simpson" and n % 2):
        raise SolveServiceError("unsupported subinterval count")
    x = Symbol(variable)
    expr = parse_expression(expr_text, [variable])
    if expr.free_symbols - {x}:
        raise SolveServiceError("integrand has another letter")
    a, b = exact_number(low), exact_number(high)
    h = simplify((b - a) / n)
    if rule == "midpoint":
        nodes = [a + (i + Rational(1, 2)) * h for i in range(n)]
        weights, factor = [Integer(1)] * n, h
    elif rule == "left":
        nodes, weights, factor = [a + i * h for i in range(n)], [Integer(1)] * n, h
    elif rule == "right":
        nodes, weights, factor = [a + i * h for i in range(1, n + 1)], [Integer(1)] * n, h
    elif rule in {"trapezoid", "simpson"}:
        nodes = [a + i * h for i in range(n + 1)]
        inner = (
            [Integer(2)] * (n - 1)
            if rule == "trapezoid"
            else [Integer(4) if i % 2 else Integer(2) for i in range(1, n)]
        )
        weights = [Integer(1), *inner, Integer(1)]
        factor = h / 2 if rule == "trapezoid" else h / 3
    else:
        raise SolveServiceError(f"unknown rule {rule}")
    values = [simplify(expr.subs(x, node)) for node in nodes]
    if any(not value.is_finite for value in values):
        raise SolveServiceError("integrand undefined at a node")
    total = simplify(factor * sum(w * v for w, v in zip(weights, values, strict=True)))
    return RuleSum(rule, h, tuple(nodes), tuple(weights), tuple(values), simplify(factor), total)


def newton_iterates(expr_text: str, variable: str, start: str, steps: int) -> tuple[Any, ...]:
    """``x_0, x_1, …, x_steps`` of Newton's method on f = ``expr_text``, exactly."""
    if not 1 <= steps <= MAX_STEPS:
        raise SolveServiceError("unsupported step count")
    x = Symbol(variable)
    f = parse_expression(expr_text, [variable])
    if f.free_symbols - {x}:
        raise SolveServiceError("function has another letter")
    slope = diff(f, x)
    iterates = [exact_number(start)]
    for _ in range(steps):
        at = iterates[-1]
        rise, run = simplify(f.subs(x, at)), simplify(slope.subs(x, at))
        if run == 0 or not (rise.is_finite and run.is_finite):
            raise SolveServiceError("the derivative vanishes at an iterate")
        iterates.append(simplify(at - rise / run))
    return tuple(iterates)


def euler_points(
    rate_text: str, start_x: str, start_y: str, step: str, steps: int
) -> tuple[tuple[Any, Any], ...]:
    """``(x_k, y_k)`` of Euler's method on y' = ``rate_text`` from (start_x, start_y)."""
    if not 1 <= steps <= MAX_SUBINTERVALS:
        raise SolveServiceError("unsupported step count")
    x, y = Symbol("x"), Symbol("y")
    rate = parse_expression(rate_text, ["x", "y"])
    if rate.free_symbols - {x, y}:
        raise SolveServiceError("rate has another letter")
    h = exact_number(step)
    points = [(exact_number(start_x), exact_number(start_y))]
    for _ in range(steps):
        at_x, at_y = points[-1]
        slope = simplify(rate.subs({x: at_x, y: at_y}))
        if not slope.is_finite:
            raise SolveServiceError("rate undefined at a step")
        points.append((simplify(at_x + h), simplify(at_y + h * slope)))
    return tuple(points)


def value_tex(value: Any) -> str:
    """``2.75`` for 11/4, ``\\frac{7}{3} \\approx 2.33333``, ``\\approx 1.21828`` for e - 1.5."""
    if value.is_Integer:
        return str(value)
    if value.is_Rational:
        if _terminates(value):
            return _decimal(value)
        return rf"{latex(value)} \approx {_decimal(value)}"
    return rf"\approx {_decimal(value)}"


def plain_tex(value: Any) -> str:
    """A value inside working: exact when short (``0.25``, ``\\frac{1}{3}``), else a decimal."""
    if value.is_Integer or (value.is_Rational and _terminates(value)):
        return _decimal(value)
    if value.is_Rational and len(str(value)) <= 9:
        return str(latex(value))
    return _decimal(value)


def decimal_tex(value: Any) -> str:
    """The value as a decimal: exact when it terminates, else to six significant figures."""
    return _decimal(value)


def _terminates(value: Any) -> bool:
    q = int(value.q)
    for prime in (2, 5):
        while q % prime == 0:
            q //= prime
    return q == 1 and len(str(value.p)) + len(str(value.q)) <= 14


def _decimal(value: Any) -> str:
    if value.is_Integer:
        return str(value)
    if value.is_Rational and _terminates(value):
        whole = str(value.evalf(30)).rstrip("0").rstrip(".")
        return whole or "0"
    text = f"{float(value.evalf(20)):.{_SIGNIFICANT}g}"
    return text if "e" not in text else str(latex(value.evalf(_SIGNIFICANT)))
