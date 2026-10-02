# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Zero-order, second-order, rate-law, and two-point Arrhenius solvers."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers.common_chem import (
    const,
    inp,
    num,
    verified,
)
from app.modules.chemistry.solvers.constants import GAS_R_J
from app.modules.chemistry.solvers.params import require, require_all
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

_ARRHENIUS = ("k1", "t1", "k2", "t2")
_NEGATIVE = "kinetics inputs are missing or negative"
_HALF_LIFE_INPUTS = "half-life inputs must be positive"
# The half-life question gives k without a time unit, so the answer is in that unit.
_TIME_OF_K = " (in the time unit of k)"


def _order_from_change(rate1: float, rate2: float, left: float, right: float) -> int:
    if left <= 0 or right <= 0 or rate1 <= 0 or rate2 <= 0 or left == right:
        raise SolveServiceError("rate-law experiments need positive changing concentrations")
    order = math.log(rate2 / rate1) / math.log(right / left)
    rounded = round(order)
    if abs(order - rounded) > 0.05:
        raise SolveServiceError("reaction order is not an integer")
    return int(rounded)


def solve_zero_order(intent: ChemistryIntent) -> ChemistryResult:
    initial, rate, time = require_all(
        intent, "initial", "rate_constant", "time", non_negative=True, message=_NEGATIVE
    )
    final = initial - rate * time
    if final < 0:
        raise SolveServiceError("zero-order concentration would be negative")
    shown = f"[A]ₜ = {num(final)} mol/L"
    return verified(
        "Verified zero-order concentration",
        (f"[A]₀ = {inp(initial)} mol/L", f"k = {inp(rate)}", f"t = {inp(time)}"),
        "[A]ₜ",
        "Integrated zero-order rate law",
        "[A]ₜ = [A]₀ − kt",
        (f"[A]ₜ = {inp(initial)} − ({inp(rate)})({inp(time)})",),
        shown,
        shown,
    )


def solve_second_order(intent: ChemistryIntent) -> ChemistryResult:
    initial, rate, time = require_all(
        intent, "initial", "rate_constant", "time", non_negative=True, message=_NEGATIVE
    )
    if initial <= 0:
        raise SolveServiceError("initial concentration must be positive")
    reciprocal = 1 / initial + rate * time
    final = 1 / reciprocal
    shown = f"[A]ₜ = {num(final)} mol/L"
    return verified(
        "Verified second-order concentration",
        (f"[A]₀ = {inp(initial)} mol/L", f"k = {inp(rate)}", f"t = {inp(time)}"),
        "[A]ₜ",
        "Integrated second-order rate law",
        "1/[A]ₜ = 1/[A]₀ + kt",
        (
            f"1/[A]ₜ = 1/({inp(initial)}) + ({inp(rate)})({inp(time)}) = {num(reciprocal)}",
            f"[A]ₜ = 1 / {num(reciprocal)}",
        ),
        shown,
        shown,
    )


def solve_zero_half_life(intent: ChemistryIntent) -> ChemistryResult:
    initial, rate = require_all(
        intent,
        "initial",
        "rate_constant",
        positive=True,
        message="half-life inputs must be positive",
    )
    shown = f"t₁/₂ = {num(initial / (2 * rate))}{_TIME_OF_K}"
    return verified(
        "Verified zero-order half-life",
        (f"[A]₀ = {inp(initial)} mol/L", f"k = {inp(rate)}"),
        "Half-life",
        "Zero-order half-life",
        "t₁/₂ = [A]₀ / (2k)",
        (f"t₁/₂ = {inp(initial)} / (2({inp(rate)}))",),
        shown,
        shown,
    )


def solve_second_half_life(intent: ChemistryIntent) -> ChemistryResult:
    initial, rate = require_all(
        intent,
        "initial",
        "rate_constant",
        positive=True,
        message="half-life inputs must be positive",
    )
    shown = f"t₁/₂ = {num(1 / (rate * initial))}{_TIME_OF_K}"
    return verified(
        "Verified second-order half-life",
        (f"[A]₀ = {inp(initial)} mol/L", f"k = {inp(rate)}"),
        "Half-life",
        "Second-order half-life",
        "t₁/₂ = 1 / (k[A]₀)",
        (f"t₁/₂ = 1 / (({inp(rate)})({inp(initial)}))",),
        shown,
        shown,
    )


def solve_rate_law(intent: ChemistryIntent) -> ChemistryResult:
    a1, rate1, a2, rate2 = require_all(
        intent, "a1", "rate1", "a2", "rate2", message="rate law needs two experiments"
    )
    b1 = intent.params.get("b1")
    b2 = intent.params.get("b2")
    if b1 is not None and b2 is not None and abs(a1 - a2) > 1e-12:
        if abs(b1 - b2) > 1e-12:
            raise SolveServiceError("only one concentration may change between experiments")
        # Two points with [B] held do not measure the order in B.
        raise SolveServiceError("the order in B was not measured")
    if abs(a1 - a2) > 1e-12:
        order_a = _order_from_change(rate1, rate2, a1, a2)
        order_b = 0
        b_factor = 1.0
        changing, first, second = "A", a1, a2
    else:
        order_a = 0
        if b1 is None or b2 is None:
            raise SolveServiceError("the changing concentration is missing")
        order_b = _order_from_change(rate1, rate2, b1, b2)
        b_factor = b1**order_b
        changing, first, second = "B", b1, b2
    order = order_a or order_b
    denominator = a1**order_a * b_factor
    constant = rate1 / denominator
    terms = []
    if order_a:
        terms.append("[A]" if order_a == 1 else f"[A]^{order_a}")
    if order_b:
        terms.append("[B]" if order_b == 1 else f"[B]^{order_b}")
    body = " ".join(terms)
    shown = f"rate = {num(constant)} {body}".rstrip()
    if changing == "B":
        if b1 is None:
            raise SolveServiceError("the changing concentration is missing")
        held = b1
    else:
        held = first
    power = "" if order == 1 else f"^{order}"
    if b1 is not None and b2 is not None:
        given = (
            f"experiment 1: [A] = {inp(a1)}, [B] = {inp(b1)}, rate = {inp(rate1)}",
            f"experiment 2: [A] = {inp(a2)}, [B] = {inp(b2)}, rate = {inp(rate2)}",
        )
    else:
        given = (
            f"experiment 1: [A] = {inp(a1)}, rate = {inp(rate1)}",
            f"experiment 2: [A] = {inp(a2)}, rate = {inp(rate2)}",
        )
    return verified(
        "Verified rate law",
        given,
        "Rate law",
        "Order from two experiments",
        "order = log(rate2/rate1) / log(conc2/conc1)",
        (
            f"order in {changing} = log({inp(rate2)} / {inp(rate1)}) / log({inp(second)} / "
            f"{inp(first)}) = {order}",
            f"k = rate1 / [{changing}]{power} = {inp(rate1)} / ({inp(held)}){power} = "
            f"{num(constant)}",
        ),
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
            f"k1 = {inp(k1)}",
            f"T1 = {inp(t1)} K",
            f"k2 = {inp(k2)}",
            f"T2 = {inp(t2)} K",
        ),
        "Activation energy",
        "Two-point Arrhenius equation",
        "ln(k2/k1) = −(Ea/R)(1/T2 − 1/T1)",
        (
            f"Ea = −({const(GAS_R_J)})ln({inp(k2)} / {inp(k1)}) / (1/{inp(t2)} − 1/{inp(t1)})"
            f" = {num(energy)} J/mol",
        ),
        shown,
        shown,
    )
