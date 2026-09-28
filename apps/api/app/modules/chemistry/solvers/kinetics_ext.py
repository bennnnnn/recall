# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Zero-order, second-order, rate-law, and two-point Arrhenius solvers."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers.common_chem import (
    num,
    verified,
)
from app.modules.chemistry.solvers.physical import GAS_R_J
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import MathServiceError


def _three(intent: ChemistryIntent, a: str, b: str, c: str) -> tuple[float, float, float]:
    values = [intent.params.get(a), intent.params.get(b), intent.params.get(c)]
    if any(value is None or value < 0 for value in values):
        raise MathServiceError("kinetics inputs cannot be negative")
    return float(values[0] or 0), float(values[1] or 0), float(values[2] or 0)


def _two(intent: ChemistryIntent, a: str, b: str) -> tuple[float, float]:
    left = intent.params.get(a)
    right = intent.params.get(b)
    if left is None or right is None or left <= 0 or right <= 0:
        raise MathServiceError("half-life inputs must be positive")
    return left, right


def _four(intent: ChemistryIntent) -> tuple[float, float, float, float]:
    values = [intent.params.get(key) for key in ("a1", "rate1", "a2", "rate2")]
    if any(value is None for value in values):
        raise MathServiceError("rate law needs two experiments")
    return (
        float(values[0] or 0),
        float(values[1] or 0),
        float(values[2] or 0),
        float(values[3] or 0),
    )


def _order_from_change(rate1: float, rate2: float, left: float, right: float) -> int:
    if left <= 0 or right <= 0 or rate1 <= 0 or rate2 <= 0 or left == right:
        raise MathServiceError("rate-law experiments need positive changing concentrations")
    order = math.log(rate2 / rate1) / math.log(right / left)
    rounded = round(order)
    if abs(order - rounded) > 0.05:
        raise MathServiceError("reaction order is not an integer")
    return int(rounded)


def solve_zero_order(intent: ChemistryIntent) -> ChemistryResult:
    initial, rate, time = _three(intent, "initial", "rate_constant", "time")
    final = initial - rate * time
    if final < 0:
        raise MathServiceError("zero-order concentration would be negative")
    shown = f"[A]ₜ = {num(final)} mol/L"
    return verified(
        "Verified zero-order concentration",
        (f"[A]₀ = {num(initial)}", f"k = {num(rate)}", f"t = {num(time)}"),
        "[A]ₜ",
        "Integrated zero-order rate law",
        "[A]ₜ = [A]₀ − kt",
        (shown,),
        shown,
        shown,
    )


def solve_second_order(intent: ChemistryIntent) -> ChemistryResult:
    initial, rate, time = _three(intent, "initial", "rate_constant", "time")
    if initial <= 0:
        raise MathServiceError("initial concentration must be positive")
    final = 1 / (1 / initial + rate * time)
    shown = f"[A]ₜ = {num(final)} mol/L"
    return verified(
        "Verified second-order concentration",
        (f"[A]₀ = {num(initial)}", f"k = {num(rate)}", f"t = {num(time)}"),
        "[A]ₜ",
        "Integrated second-order rate law",
        "1/[A]ₜ = 1/[A]₀ + kt",
        (shown,),
        shown,
        shown,
    )


def solve_zero_half_life(intent: ChemistryIntent) -> ChemistryResult:
    initial, rate = _two(intent, "initial", "rate_constant")
    shown = f"t₁/₂ = {num(initial / (2 * rate))} s"
    return verified(
        "Verified zero-order half-life",
        (f"[A]₀ = {num(initial)}", f"k = {num(rate)}"),
        "Half-life",
        "Zero-order half-life",
        "t₁/₂ = [A]₀ / (2k)",
        (shown,),
        shown,
        shown,
    )


def solve_second_half_life(intent: ChemistryIntent) -> ChemistryResult:
    initial, rate = _two(intent, "initial", "rate_constant")
    shown = f"t₁/₂ = {num(1 / (rate * initial))} s"
    return verified(
        "Verified second-order half-life",
        (f"[A]₀ = {num(initial)}", f"k = {num(rate)}"),
        "Half-life",
        "Second-order half-life",
        "t₁/₂ = 1 / (k[A]₀)",
        (shown,),
        shown,
        shown,
    )


def solve_rate_law(intent: ChemistryIntent) -> ChemistryResult:
    a1, rate1, a2, rate2 = _four(intent)
    b1 = intent.params.get("b1")
    b2 = intent.params.get("b2")
    if b1 is not None and b2 is not None and abs(a1 - a2) > 1e-12 and abs(b1 - b2) > 1e-12:
        raise MathServiceError("only one concentration may change between experiments")
    if abs(a1 - a2) > 1e-12:
        order_a = _order_from_change(rate1, rate2, a1, a2)
        order_b = 0
    else:
        order_a = 0
        if b1 is None or b2 is None:
            raise MathServiceError("the changing concentration is missing")
        order_b = _order_from_change(rate1, rate2, b1, b2)
    denominator = a1**order_a * ((b1 or 1) ** order_b)
    constant = rate1 / denominator
    terms = []
    if order_a:
        terms.append("[A]" if order_a == 1 else f"[A]^{order_a}")
    if order_b:
        terms.append("[B]" if order_b == 1 else f"[B]^{order_b}")
    body = " ".join(terms)
    shown = f"rate = {num(constant)} {body}".rstrip()
    return verified(
        "Verified rate law",
        (
            f"experiment 1: [A] = {num(a1)}, rate = {num(rate1)}",
            f"experiment 2: [A] = {num(a2)}, rate = {num(rate2)}",
        ),
        "Rate law",
        "Order from two experiments",
        "order = log(rate2/rate1) / log(conc2/conc1)",
        (shown,),
        shown,
        shown,
    )


def solve_arrhenius_two_point(intent: ChemistryIntent) -> ChemistryResult:
    k1, t1, k2, t2 = (
        intent.params.get("k1"),
        intent.params.get("t1"),
        intent.params.get("k2"),
        intent.params.get("t2"),
    )
    if None in {k1, t1, k2, t2} or min(k1 or 0, k2 or 0, t1 or 0, t2 or 0) <= 0 or t1 == t2:
        raise MathServiceError("two-point Arrhenius needs two positive rates and temperatures")
    energy = -GAS_R_J * math.log((k2 or 1) / (k1 or 1)) / (1 / (t2 or 1) - 1 / (t1 or 1))
    shown = f"Ea = {num(energy / 1000)} kJ/mol"
    return verified(
        "Verified two-temperature Arrhenius",
        (
            f"k1 = {num(k1 or 0)}",
            f"T1 = {num(t1 or 0)} K",
            f"k2 = {num(k2 or 0)}",
            f"T2 = {num(t2 or 0)} K",
        ),
        "Activation energy",
        "Two-point Arrhenius equation",
        "ln(k2/k1) = −(Ea/R)(1/T2 − 1/T1)",
        (shown,),
        shown,
        shown,
    )
