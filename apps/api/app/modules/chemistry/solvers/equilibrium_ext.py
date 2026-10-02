# ruff: noqa: RUF001, RUF002 -- textbook chemistry uses Greek nu and minus signs.
"""Solubility, Kp, and quadratic ICE equilibria."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from app.models.schemas.chemistry import ChemistryIntent
from app.models.schemas.chemistry.scene import EquilibriumRow, EquilibriumScene
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.solvers.common_chem import const, inp, num, verified
from app.modules.chemistry.solvers.constants import GAS_R
from app.modules.chemistry.solvers.physical import equilibrium_expression
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.species import counts_in_mass_action, parse_species
from app.services.solving import SolveServiceError


def _ions(equation: str) -> list[tuple[str, int]]:
    balanced = balance_equation(equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "solubility equation could not be balanced")
    ions = [
        (species, coefficient)
        for species, coefficient in balanced.products.items()
        if counts_in_mass_action(species)
    ]
    if not ions:
        raise SolveServiceError("solubility products need at least one aqueous ion")
    return ions


def _solubility_power(ions: list[tuple[str, int]]) -> tuple[float, int]:
    factor = 1.0
    power = 0
    for _species, coefficient in ions:
        factor *= coefficient**coefficient
        power += coefficient
    return factor, power


def _ion_product_text(ions: list[tuple[str, int]]) -> str:
    """``Ksp = [Ca2+][OH-]^2 = (s)(2s)^2 = 4s^3`` for the ions of a salt with solubility s."""
    factor, power = _solubility_power(ions)
    bracketed = "".join(
        f"[{species}]" + ("" if coefficient == 1 else f"^{coefficient}")
        for species, coefficient in ions
    )
    in_s = "".join(
        f"({'' if coefficient == 1 else coefficient}s)"
        + ("" if coefficient == 1 else f"^{coefficient}")
        for _species, coefficient in ions
    )
    collected = f"{num(factor)}s" if factor != 1 else "s"
    collected += "" if power == 1 else f"^{power}"
    return f"Ksp = {bracketed} = {in_s} = {collected}"


def solve_ksp(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise SolveServiceError("a solubility equation is required")
    ions = _ions(intent.equation)
    factor, power = _solubility_power(ions)
    ksp = intent.params.get("ksp")
    solubility = intent.params.get("solubility")
    lines = [_ion_product_text(ions)]
    if ksp is not None and solubility is None:
        if ksp <= 0:
            raise SolveServiceError("Ksp must be positive")
        value = (ksp / factor) ** (1 / power)
        shown = f"s = {num(value)} mol/L"
        detail = f"Ksp = {inp(ksp)}"
        divisor = "" if factor == 1 else f" / {num(factor)}"
        lines.append(f"s = (Ksp{divisor})^(1/{power}) = (({inp(ksp)}){divisor})^(1/{power})")
    elif solubility is not None and ksp is None:
        if solubility <= 0:
            raise SolveServiceError("solubility must be positive")
        value = factor * solubility**power
        shown = f"Ksp = {num(value)}"
        detail = f"s = {inp(solubility)} mol/L"
        lines.append(f"Ksp = ({num(factor)})({inp(solubility)})^{power}")
    else:
        raise SolveServiceError("give Ksp or the molar solubility, not both")
    return verified(
        "Verified solubility product",
        (intent.equation, detail),
        "Molar solubility" if ksp is not None else "Ksp",
        *stated("ksp"),
        lines,
        shown,
        num(value),
    )


def solve_precipitation(intent: ChemistryIntent) -> ChemistryResult:
    qsp = intent.params.get("qsp")
    ksp = intent.params.get("ksp")
    if qsp is None or ksp is None or qsp < 0 or ksp <= 0:
        raise SolveServiceError("precipitation needs a non-negative Qsp and a positive Ksp")
    if math.isclose(qsp, ksp, rel_tol=1e-9, abs_tol=0.0):
        relation = "saturated (Qsp = Ksp)"
    elif qsp > ksp:
        relation = "precipitate forms (Qsp > Ksp)"
    else:
        relation = "no precipitate (Qsp < Ksp)"
    return verified(
        "Verified precipitation check",
        (f"Qsp = {inp(qsp)}", f"Ksp = {inp(ksp)}"),
        "Whether a precipitate forms",
        *stated("precipitation"),
        (
            f"Qsp = {inp(qsp)} {'=' if 'saturated' in relation else '>' if qsp > ksp else '<'} "
            f"Ksp = {inp(ksp)}",
        ),
        relation,
        relation,
    )


def solve_common_ion(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise SolveServiceError("a solubility equation is required")
    ksp = intent.params.get("ksp")
    if ksp is None or ksp <= 0:
        raise SolveServiceError("Ksp must be positive")
    ions = _ions(intent.equation)
    unknown = [species for species, _coefficient in ions if species not in intent.species]
    if len(unknown) != 1:
        raise SolveServiceError("exactly one ion concentration must be unknown")
    target = unknown[0]
    power = dict(ions)[target]
    known = 1.0
    for species, coefficient in ions:
        if species == target:
            continue
        concentration = intent.species[species]
        if concentration <= 0:
            raise SolveServiceError(f"{species} concentration must be positive")
        known *= concentration**coefficient
    value = (ksp / known) ** (1 / power)
    shown = f"[{target}] = {num(value)} mol/L"
    given = [f"Ksp = {inp(ksp)}"]
    given.extend(f"[{name}] = {inp(amount)} mol/L" for name, amount in intent.species.items())
    parts = [
        f"({inp(intent.species[species])})" + ("" if coefficient == 1 else f"^{coefficient}")
        for species, coefficient in ions
        if species != target
    ]
    others = parts[0] if len(parts) == 1 else f"({' × '.join(parts)})"
    root = "" if power == 1 else f"^(1/{power})"
    working = f"[{target}] = (({inp(ksp)}) / {others}){root}"
    return verified(
        "Verified common-ion concentration",
        given,
        f"[{target}]",
        *stated("common_ion"),
        (
            _ion_product_text_from_species(ions),
            working,
            f"molar solubility s = [{target}] / {power} = {num(value / power)} mol/L",
        ),
        shown,
        num(value),
    )


def _ion_product_text_from_species(ions: list[tuple[str, int]]) -> str:
    return "Ksp = " + "".join(
        f"[{species}]" + ("" if coefficient == 1 else f"^{coefficient}")
        for species, coefficient in ions
    )


def solve_kp(intent: ChemistryIntent) -> ChemistryResult:
    value_num, expression, substitution = equilibrium_expression(intent, pressure=True)
    value = num(value_num)
    return verified(
        "Verified Kp",
        tuple(
            f"P({species}) = {inp(pressure)} atm" for species, pressure in intent.species.items()
        ),
        "Kp",
        stated("kp")[0],
        f"Kp = {expression}",
        (f"Kp = {substitution}",),
        f"Kp = {value}",
        value,
    )


def _gas_delta_n(equation: str) -> int:
    balanced = balance_equation(equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "equation could not be balanced")

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
        raise SolveServiceError("temperature must be positive Kelvin")
    if "delta_n" in intent.params:
        delta_n = int(intent.params["delta_n"])
    elif intent.equation:
        delta_n = _gas_delta_n(intent.equation)
    else:
        raise SolveServiceError("Kc/Kp conversion needs Δn or an equation")
    factor = (GAS_R * temperature) ** delta_n
    kc = intent.params.get("kc")
    kp = intent.params.get("kp")
    if kc is not None and kp is None:
        value = kc * factor
        shown = f"Kp = {num(value)}"
        given = f"Kc = {inp(kc)}"
        working = f"Kp = ({inp(kc)})({num(GAS_R * temperature)})^{delta_n}"
    elif kp is not None and kc is None:
        if factor == 0:
            raise SolveServiceError("cannot convert that Kp")
        value = kp / factor
        shown = f"Kc = {num(value)}"
        given = f"Kp = {inp(kp)}"
        working = f"Kc = ({inp(kp)}) / ({num(GAS_R * temperature)})^{delta_n}"
    else:
        raise SolveServiceError("give Kc or Kp, not both")
    return verified(
        "Verified Kc/Kp conversion",
        (given, f"T = {inp(temperature)} K", f"Δn = {delta_n}"),
        shown.split(" = ", 1)[0],
        *stated("kc_kp"),
        (
            f"RT = ({const(GAS_R)})({inp(temperature)}) = {num(GAS_R * temperature)} L·atm/mol",
            working,
        ),
        shown,
        num(value),
    )


def solve_ice(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise SolveServiceError("an equilibrium equation is required")
    constant = intent.params.get("k")
    if constant is None or constant <= 0:
        raise SolveServiceError("K must be positive")
    balanced = balance_equation(intent.equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "equation could not be balanced")
    from sympy import N, Symbol, expand

    extent = Symbol("x")
    concentrations: dict[str, Any] = {}
    for species, coefficient in balanced.reactants.items():
        if counts_in_mass_action(species):
            if species not in intent.species:
                raise SolveServiceError(f"the starting concentration of {species} is missing")
            concentrations[species] = intent.species[species] - coefficient * extent
    for species, coefficient in balanced.products.items():
        if counts_in_mass_action(species):
            concentrations[species] = intent.species.get(species, 0.0) + coefficient * extent
    if not concentrations:
        raise SolveServiceError("the equilibrium has no concentration terms")
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
        raise SolveServiceError("equilibrium extent is higher than quadratic")
    roots = poly.nroots() if poly.degree() > 0 else []
    # Tolerances follow the size of the concentrations, so a 1e-9 M problem is not
    # judged by a 1e-6 M yardstick.
    scale = max((abs(value) for value in intent.species.values()), default=0.0) or 1.0
    valid: list[float] = []
    for root in roots:
        numeric = complex(N(root))
        if abs(numeric.imag) > 1e-7 * scale:
            continue
        candidate = float(numeric.real)
        negative = -1e-8 * scale
        if any(
            float(N(expr.subs(extent, candidate))) < negative for expr in concentrations.values()
        ):
            continue
        if not any(abs(candidate - kept) <= 1e-6 * scale for kept in valid):
            valid.append(candidate)
    if len(valid) != 1:
        raise SolveServiceError("equilibrium extent is not unique")
    chosen = valid[0]
    equilibrium: dict[str, str] = {}
    results: list[str] = []
    for species, expression in concentrations.items():
        amount = float(N(expression.subs(extent, chosen)))
        shown = f"{num(amount)} mol/L"
        results.append(f"[{species}] = {shown}")
        equilibrium[species] = shown
    rows = _ice_rows(intent, balanced.reactants, balanced.products, equilibrium)
    lines = [
        *_ice_setup(intent, balanced.reactants, balanced.products, concentrations),
        f"K = {_ice_expression(balanced.reactants, balanced.products, concentrations)} = "
        f"{inp(constant)}",
        f"K = {_ice_substituted(intent, balanced.reactants, balanced.products, concentrations)}",
        f"{_polynomial_text(poly.all_coeffs())} = 0",
        f"x = {num(chosen)} (the root that keeps every concentration non-negative)",
    ]
    answer = "\n".join([f"x = {num(chosen)}", *results])
    quotient = _ice_substituted(intent, balanced.reactants, balanced.products, concentrations)
    result = verified(
        "Verified ICE equilibrium",
        (intent.equation, f"K = {inp(constant)}"),
        "Equilibrium extent and concentrations",
        stated("ice_equilibrium")[0],
        f"K = {quotient}",
        lines,
        answer,
        num(chosen),
    )
    return replace(result, scene=EquilibriumScene(title="ICE table", rows=rows))


def _extent_text(initial: float, coefficient: int, *, product: bool) -> str:
    """One species at equilibrium in terms of the extent x: ``2x``, ``1 − x``, ``0.1 + x``."""
    change = "x" if coefficient == 1 else f"{coefficient}x"
    if initial == 0 and product:
        return change
    return f"{inp(initial)} {'+' if product else '−'} {change}"


def _ice_setup(
    intent: ChemistryIntent,
    reactants: dict[str, int],
    products: dict[str, int],
    concentrations: dict[str, Any],
) -> list[str]:
    """``[N2O4] = 1 − x`` for each species: initial concentration plus its change."""
    lines = []
    for side, product in ((reactants, False), (products, True)):
        for species, coefficient in side.items():
            if species in concentrations:
                initial = intent.species.get(species, 0.0)
                lines.append(f"[{species}] = {_extent_text(initial, coefficient, product=product)}")
    return lines


def _ice_expression(
    reactants: dict[str, int], products: dict[str, int], concentrations: dict[str, Any]
) -> str:
    """The mass-action expression as written in the concentrations: ``[NO2]^2 / [N2O4]``."""

    def side(terms: dict[str, int]) -> str:
        parts = [
            f"[{species}]" + ("" if coefficient == 1 else f"^{coefficient}")
            for species, coefficient in terms.items()
            if species in concentrations
        ]
        text = " × ".join(parts) or "1"
        return f"({text})" if len(parts) > 1 else text

    return f"{side(products)} / {side(reactants)}"


def _ice_substituted(
    intent: ChemistryIntent,
    reactants: dict[str, int],
    products: dict[str, int],
    concentrations: dict[str, Any],
) -> str:
    """``(2x)^2 / (1 − x)``: each concentration replaced by its expression in x."""

    def side(terms: dict[str, int], *, product: bool) -> str:
        parts = []
        for species, coefficient in terms.items():
            if species not in concentrations:
                continue
            expression = _extent_text(
                intent.species.get(species, 0.0), coefficient, product=product
            )
            parts.append(f"({expression})" + ("" if coefficient == 1 else f"^{coefficient}"))
        text = " × ".join(parts) or "1"
        return f"({text})" if len(parts) > 1 else text

    return f"{side(products, product=True)} / {side(reactants, product=False)}"


def _polynomial_text(coefficients: list[Any]) -> str:
    """``4x^2 + 4x − 4`` from sympy's highest-degree-first coefficients."""
    degree = len(coefficients) - 1
    text = ""
    for offset, coefficient in enumerate(coefficients):
        value = float(coefficient)
        if abs(value) < 1e-15:
            continue
        power = degree - offset
        magnitude = num(abs(value))
        term = magnitude if power == 0 else ("x" if power == 1 else f"x^{power}")
        if power and abs(abs(value) - 1) < 1e-12:
            body = term
        elif power:
            body = f"{magnitude}{term}"
        else:
            body = term
        sign = "−" if value < 0 else "+"
        text += f"−{body}" if not text and value < 0 else body if not text else f" {sign} {body}"
    return text or "0"


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
