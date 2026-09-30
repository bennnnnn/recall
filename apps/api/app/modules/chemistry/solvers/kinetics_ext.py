# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Zero-order, second-order, rate-law, and two-point Arrhenius solvers."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers.common_chem import (
    num,
    verified,
)
from app.modules.chemistry.solvers.params import require
from app.modules.chemistry.solvers.physical import GAS_R_J
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

_ARRHENIUS = ("k1", "t1", "k2", "t2")
# The half-life question gives k without a time unit, so the answer is in that unit.
_TIME_OF_K = " (in the time unit of k)"


def _three(intent: ChemistryIntent, a: str, b: str, c: str) -> tuple[float, float, float]:
    message = "kinetics inputs are missing or negative"
    return (
        require(intent, a, non_negative=True, message=message),
        require(intent, b, non_negative=True, message=message),
        require(intent, c, non_negative=True, message=message),
    )


def _two(intent: ChemistryIntent, a: str, b: str) -> tuple[float, float]:
    left = intent.params.get(a)
    right = intent.params.get(b)
    if left is None or right is None or left <= 0 or right <= 0:
        raise SolveServiceError("half-life inputs must be positive")
    return left, right


def _four(intent: ChemistryIntent) -> tuple[float, float, float, float]:
    message = "rate law needs two experiments"
    return (
        require(intent, "a1", message=message),
        require(intent, "rate1", message=message),
        require(intent, "a2", message=message),
        require(intent, "rate2", message=message),
    )


def _order_from_change(rate1: float, rate2: float, left: float, right: float) -> int:
    if left <= 0 or right <= 0 or rate1 <= 0 or rate2 <= 0 or left == right:
        raise SolveServiceError("rate-law experiments need positive changing concentrations")
    order = math.log(rate2 / rate1) / math.log(right / left)
    rounded = round(order)
    if abs(order - rounded) > 0.05:
        raise SolveServiceError("reaction order is not an integer")
    return int(rounded)


def solve_zero_order(intent: ChemistryIntent) -> ChemistryResult:
    initial, rate, time = _three(intent, "initial", "rate_constant", "time")
    final = initial - rate * time
    if final < 0:
        raise SolveServiceError("zero-order concentration would be negative")
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
        raise SolveServiceError("initial concentration must be positive")
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
    shown = f"t₁/₂ = {num(initial / (2 * rate))}{_TIME_OF_K}"
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
    shown = f"t₁/₂ = {num(1 / (rate * initial))}{_TIME_OF_K}"
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
        raise SolveServiceError("only one concentration may change between experiments")
    if abs(a1 - a2) > 1e-12:
        order_a = _order_from_change(rate1, rate2, a1, a2)
        order_b = 0
        b_factor = 1.0
    else:
        order_a = 0
        if b1 is None or b2 is None:
            raise SolveServiceError("the changing concentration is missing")
        order_b = _order_from_change(rate1, rate2, b1, b2)
        b_factor = b1**order_b
    denominator = a1**order_a * b_factor
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
    message = "two-point Arrhenius needs two positive rates and temperatures"
    k1, t1, k2, t2 = (require(intent, key, positive=True, message=message) for key in _ARRHENIUS)
    if t1 == t2:
        raise SolveServiceError(message)
    energy = -GAS_R_J * math.log(k2 / k1) / (1 / t2 - 1 / t1)
    shown = f"Ea = {num(energy / 1000)} kJ/mol"
    return verified(
        "Verified two-temperature Arrhenius",
        (
            f"k1 = {num(k1)}",
            f"T1 = {num(t1)} K",
            f"k2 = {num(k2)}",
            f"T2 = {num(t2)} K",
        ),
        "Activation energy",
        "Two-point Arrhenius equation",
        "ln(k2/k1) = −(Ea/R)(1/T2 − 1/T1)",
        (shown,),
        shown,
        shown,
    )
