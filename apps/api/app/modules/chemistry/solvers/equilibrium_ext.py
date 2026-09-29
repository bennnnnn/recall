# ruff: noqa: RUF001 -- textbook chemistry uses Greek nu in mass-action formulas.
"""Solubility, Kp, and quadratic ICE equilibria."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from app.models.schemas.chemistry import ChemistryIntent
from app.models.schemas.chemistry.scene import EquilibriumRow, EquilibriumScene
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.solvers.common_chem import num, verified
from app.modules.chemistry.solvers.physical import _equilibrium_expression
from app.modules.chemistry.solvers.solutions import GAS_R
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.species import counts_in_mass_action, parse_species
from app.services.solving import MathServiceError


def _ions(equation: str) -> list[tuple[str, int]]:
    balanced = balance_equation(equation)
    if not balanced.balanced:
        raise MathServiceError(balanced.error or "solubility equation could not be balanced")
    ions = [
        (species, coefficient)
        for species, coefficient in balanced.products.items()
        if counts_in_mass_action(species)
    ]
    if not ions:
        raise MathServiceError("solubility products need at least one aqueous ion")
    return ions


def _solubility_power(ions: list[tuple[str, int]]) -> tuple[float, int]:
    factor = 1.0
    power = 0
    for _species, coefficient in ions:
        factor *= coefficient**coefficient
        power += coefficient
    return factor, power


def solve_ksp(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise MathServiceError("a solubility equation is required")
    ions = _ions(intent.equation)
    factor, power = _solubility_power(ions)
    ksp = intent.params.get("ksp")
    solubility = intent.params.get("solubility")
    if ksp is not None and solubility is None:
        if ksp <= 0:
            raise MathServiceError("Ksp must be positive")
        value = (ksp / factor) ** (1 / power)
        shown = f"s = {num(value)} mol/L"
        detail = f"Ksp = {num(ksp)}"
    elif solubility is not None and ksp is None:
        if solubility <= 0:
            raise MathServiceError("solubility must be positive")
        value = factor * solubility**power
        shown = f"Ksp = {num(value)}"
        detail = f"s = {num(solubility)} mol/L"
    else:
        raise MathServiceError("give Ksp or the molar solubility, not both")
    return verified(
        "Verified solubility product",
        (intent.equation, detail),
        "Molar solubility" if ksp is not None else "Ksp",
        "Solubility product",
        "Ksp = Π (νᵢ s)^νᵢ",
        (shown,),
        shown,
        num(value),
    )


def solve_precipitation(intent: ChemistryIntent) -> ChemistryResult:
    qsp = intent.params.get("qsp")
    ksp = intent.params.get("ksp")
    if qsp is None or ksp is None or qsp < 0 or ksp <= 0:
        raise MathServiceError("precipitation needs a non-negative Qsp and a positive Ksp")
    if math.isclose(qsp, ksp, rel_tol=1e-9, abs_tol=0.0):
        relation = "saturated (Qsp = Ksp)"
    elif qsp > ksp:
        relation = "precipitate forms (Qsp > Ksp)"
    else:
        relation = "no precipitate (Qsp < Ksp)"
    return verified(
        "Verified precipitation check",
        (f"Qsp = {num(qsp)}", f"Ksp = {num(ksp)}"),
        "Whether a precipitate forms",
        "Ion product versus solubility product",
        "compare Qsp with Ksp",
        (relation,),
        relation,
        relation,
    )


def solve_common_ion(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise MathServiceError("a solubility equation is required")
    ksp = intent.params.get("ksp")
    if ksp is None or ksp <= 0:
        raise MathServiceError("Ksp must be positive")
    ions = _ions(intent.equation)
    unknown = [species for species, _coefficient in ions if species not in intent.species]
    if len(unknown) != 1:
        raise MathServiceError("exactly one ion concentration must be unknown")
    target = unknown[0]
    power = dict(ions)[target]
    known = 1.0
    for species, coefficient in ions:
        if species == target:
            continue
        concentration = intent.species[species]
        if concentration <= 0:
            raise MathServiceError(f"{species} concentration must be positive")
        known *= concentration**coefficient
    value = (ksp / known) ** (1 / power)
    shown = f"[{target}] = {num(value)} mol/L"
    given = [f"Ksp = {num(ksp)}"]
    given.extend(f"[{name}] = {num(amount)}" for name, amount in intent.species.items())
    return verified(
        "Verified common-ion concentration",
        given,
        f"[{target}]",
        "Common-ion effect",
        "Ksp = Π [ion]^ν",
        (shown,),
        shown,
        num(value),
    )


def solve_kp(intent: ChemistryIntent) -> ChemistryResult:
    value_num, expression, substitution = _equilibrium_expression(intent, pressure=True)
    value = num(value_num)
    return verified(
        "Verified Kp",
        tuple(
            f"P({species}) = {num(pressure)} atm" for species, pressure in intent.species.items()
        ),
        "Kp",
        "Partial-pressure equilibrium constant",
        f"Kp = {expression}",
        (f"Kp = {substitution}",),
        f"Kp = {value}",
        value,
    )


def _gas_delta_n(equation: str) -> int:
    balanced = balance_equation(equation)
    if not balanced.balanced:
        raise MathServiceError(balanced.error or "equation could not be balanced")

    def _count(side: dict[str, int]) -> int:
        total = 0
        for label, coefficient in side.items():
            species = parse_species(label, coefficient_already_removed=True)
            if species is not None and species.phase in {"s", "l", "aq"}:
                continue
            total += coefficient
        return total

    return _count(balanced.products) - _count(balanced.reactants)


def solve_kc_kp(intent: ChemistryIntent) -> ChemistryResult:
    temperature = intent.params.get("temperature")
    if temperature is None or temperature <= 0:
        raise MathServiceError("temperature must be positive Kelvin")
    if "delta_n" in intent.params:
        delta_n = int(intent.params["delta_n"])
    elif intent.equation:
        delta_n = _gas_delta_n(intent.equation)
    else:
        raise MathServiceError("Kc/Kp conversion needs Δn or an equation")
    factor = (GAS_R * temperature) ** delta_n
    kc = intent.params.get("kc")
    kp = intent.params.get("kp")
    if kc is not None and kp is None:
        value = kc * factor
        shown = f"Kp = {num(value)}"
        given = f"Kc = {num(kc)}"
    elif kp is not None and kc is None:
        if factor == 0:
            raise MathServiceError("cannot convert that Kp")
        value = kp / factor
        shown = f"Kc = {num(value)}"
        given = f"Kp = {num(kp)}"
    else:
        raise MathServiceError("give Kc or Kp, not both")
    return verified(
        "Verified Kc/Kp conversion",
        (given, f"T = {num(temperature)} K", f"Δn = {delta_n}"),
        shown.split(" = ", 1)[0],
        "Concentration and pressure equilibrium constants",
        "Kp = Kc (RT)^Δn",
        (f"RT = {num(GAS_R * temperature)} L·atm/(mol·K)", shown),
        shown,
        num(value),
    )


def solve_ice(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise MathServiceError("an equilibrium equation is required")
    constant = intent.params.get("k")
    if constant is None or constant <= 0:
        raise MathServiceError("K must be positive")
    balanced = balance_equation(intent.equation)
    if not balanced.balanced:
        raise MathServiceError(balanced.error or "equation could not be balanced")
    from sympy import N, Symbol, expand

    extent = Symbol("x")
    concentrations: dict[str, Any] = {}
    for species, coefficient in balanced.reactants.items():
        if counts_in_mass_action(species):
            concentrations[species] = intent.species.get(species, 0.0) - coefficient * extent
    for species, coefficient in balanced.products.items():
        if counts_in_mass_action(species):
            concentrations[species] = intent.species.get(species, 0.0) + coefficient * extent
    if not concentrations:
        raise MathServiceError("the equilibrium has no concentration terms")
    numerator = 1
    denominator = 1
    for species, coefficient in balanced.products.items():
        if species in concentrations:
            numerator *= concentrations[species] ** coefficient
    for species, coefficient in balanced.reactants.items():
        if species in concentrations:
            denominator *= concentrations[species] ** coefficient
    polynomial = expand(numerator - constant * denominator)
    poly = polynomial.as_poly(extent)
    if poly is None or poly.degree() > 2:
        raise MathServiceError("equilibrium extent is higher than quadratic")
    roots = poly.nroots() if poly.degree() > 0 else []
    valid: list[float] = []
    for root in roots:
        numeric = complex(N(root))
        if abs(numeric.imag) > 1e-7:
            continue
        candidate = float(numeric.real)
        if any(float(N(expr.subs(extent, candidate))) < -1e-8 for expr in concentrations.values()):
            continue
        if not any(abs(candidate - kept) <= 1e-6 for kept in valid):
            valid.append(candidate)
    if len(valid) != 1:
        raise MathServiceError("equilibrium extent is not unique")
    chosen = valid[0]
    lines = [f"x = {num(chosen)}"]
    equilibrium: dict[str, str] = {}
    for species, expression in concentrations.items():
        amount = float(N(expression.subs(extent, chosen)))
        shown = f"{num(amount)} mol/L"
        lines.append(f"[{species}] = {shown}")
        equilibrium[species] = shown
    rows = _ice_rows(intent, balanced.reactants, balanced.products, equilibrium)
    answer = "; ".join(lines)
    result = verified(
        "Verified ICE equilibrium",
        (intent.equation, f"K = {num(constant)}"),
        "Equilibrium extent and concentrations",
        "ICE table, quadratic or linear",
        "K from the extent x",
        lines,
        answer,
        num(chosen),
    )
    return replace(result, scene=EquilibriumScene(title="ICE table", rows=rows))


def _ice_change(coefficient: int, *, product: bool) -> str:
    magnitude = "x" if coefficient == 1 else f"{coefficient}x"
    return f"+{magnitude}" if product else f"−{magnitude}"


def _ice_rows(
    intent: ChemistryIntent,
    reactants: dict[str, int],
    products: dict[str, int],
    equilibrium: dict[str, str],
) -> list[EquilibriumRow]:
    rows: list[EquilibriumRow] = []
    for species, coefficient in reactants.items():
        if not counts_in_mass_action(species):
            continue
        rows.append(
            EquilibriumRow(
                species=species,
                initial=num(intent.species.get(species, 0.0)),
                change=_ice_change(coefficient, product=False),
                equilibrium=equilibrium.get(species, ""),
            )
        )
    for species, coefficient in products.items():
        if not counts_in_mass_action(species):
            continue
        rows.append(
            EquilibriumRow(
                species=species,
                initial=num(intent.species.get(species, 0.0)),
                change=_ice_change(coefficient, product=True),
                equilibrium=equilibrium.get(species, ""),
            )
        )
    return rows
