# ruff: noqa: RUF001, RUF002 -- textbook formulas intentionally use Unicode math notation.
"""Thermochemistry, equilibrium, kinetics, electrochemistry, and nuclear solves."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.solvers.common_chem import const, inp, num, verified
from app.modules.chemistry.solvers.constants import FARADAY, GAS_R_J
from app.modules.chemistry.solvers.params import require_all
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError


def solve_thermochemistry(intent: ChemistryIntent) -> ChemistryResult:
    if intent.chemistry_op == "heat":
        mass, specific_heat, delta_t = require_all(intent, "mass", "specific_heat", "delta_t")
        if mass <= 0 or specific_heat <= 0:
            raise SolveServiceError("mass and specific heat must be positive")
        heat_j = mass * specific_heat * delta_t
        value = f"{num(heat_j)} J"
        substitution = f"q = ({inp(mass)})({inp(specific_heat)})({inp(delta_t)})"
        return verified(
            "Verified heat calculation",
            (
                f"m = {inp(mass)} g",
                f"c = {inp(specific_heat)} J/(g·°C)",
                f"ΔT = {inp(delta_t)} °C",
            ),
            "Heat transferred, q",
            *stated("heat"),
            (substitution,),
            f"q = {value}",
            value,
        )
    if intent.chemistry_op == "gibbs":
        delta_h, delta_s, temperature = require_all(intent, "delta_h", "delta_s", "temperature")
        if temperature <= 0:
            raise SolveServiceError("temperature must be positive Kelvin")
        # Extractors normalize both H and S to kJ-based units.
        delta_g = delta_h - temperature * delta_s
        value = f"{num(delta_g)} kJ/mol"
        substitution = f"ΔG = {inp(delta_h)} − ({inp(temperature)})({inp(delta_s)})"
        return verified(
            "Verified Gibbs free energy",
            (
                f"ΔH = {inp(delta_h)} kJ/mol",
                f"ΔS = {inp(delta_s)} kJ/(mol·K)",
                f"T = {inp(temperature)} K",
            ),
            "Gibbs free-energy change, ΔG",
            *stated("gibbs"),
            (substitution,),
            f"ΔG = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported thermochemistry operation: {intent.chemistry_op}")


def _stored_concentration(intent: ChemistryIntent, species: str) -> float | None:
    """Read a concentration stored under the species label or its unphased formula."""
    if species in intent.species:
        return intent.species[species]
    if "(" in species:
        bare = species[: species.rfind("(")]
        if bare in intent.species:
            return intent.species[bare]
    return None


def equilibrium_expression(
    intent: ChemistryIntent, *, pressure: bool = False
) -> tuple[float, str, str]:
    equation = intent.equation
    if not equation:
        raise SolveServiceError("a simple reaction equation is required")
    from app.modules.chemistry.equations import balance_equation

    balanced = balance_equation(equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "reaction could not be balanced")
    from app.modules.chemistry.species import counts_in_mass_action

    numerator = 1.0
    denominator = 1.0
    numerator_terms: list[str] = []
    denominator_terms: list[str] = []
    substitutions_top: list[str] = []
    substitutions_bottom: list[str] = []

    def _accumulate(species: str, coefficient: int, *, product: bool) -> None:
        nonlocal numerator, denominator
        if not counts_in_mass_action(species):
            return
        concentration = _stored_concentration(intent, species)
        if concentration is None or concentration <= 0:
            raise SolveServiceError(f"positive concentration required for {species}")
        label = f"P({species})" if pressure else f"[{species}]"
        power = "" if coefficient == 1 else f"^{coefficient}"
        if product:
            numerator *= concentration**coefficient
            numerator_terms.append(f"{label}{power}")
            substitutions_top.append(f"({inp(concentration)}){power}")
        else:
            denominator *= concentration**coefficient
            denominator_terms.append(f"{label}{power}")
            substitutions_bottom.append(f"({inp(concentration)}){power}")

    for species, coefficient in balanced.products.items():
        _accumulate(species, coefficient, product=True)
    for species, coefficient in balanced.reactants.items():
        _accumulate(species, coefficient, product=False)
    if not numerator_terms and not denominator_terms:
        raise SolveServiceError("the equilibrium expression has no concentration terms")
    return (
        numerator / denominator,
        _fraction(numerator_terms, denominator_terms),
        _fraction(substitutions_top, substitutions_bottom),
    )


def _fraction(top: list[str], bottom: list[str]) -> str:
    """``[HI]^2 / ([H2] × [I2])``: parentheses only around a product; a pure solid drops out."""

    def side(parts: list[str]) -> str:
        text = " × ".join(parts) or "1"
        return f"({text})" if len(parts) > 1 else text

    if not bottom:
        return side(top)
    return f"{side(top)} / {side(bottom)}"


def solve_equilibrium(intent: ChemistryIntent) -> ChemistryResult:
    value_num, expression, substitution = equilibrium_expression(intent)
    symbol = "Kc" if intent.chemistry_op == "equilibrium_constant" else "Qc"
    title = "Verified equilibrium constant" if symbol == "Kc" else "Verified reaction quotient"
    value = num(value_num)
    return verified(
        title,
        tuple(
            f"[{species}] = {inp(concentration)} mol/L"
            for species, concentration in intent.species.items()
        ),
        symbol,
        stated(intent.chemistry_op)[0],
        f"{symbol} = {expression}",
        (f"{symbol} = {substitution}",),
        f"{symbol} = {value}",
        value,
    )


def solve_kinetics(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "first_order_half_life":
        (rate_constant,) = require_all(intent, "rate_constant")
        if rate_constant <= 0:
            raise SolveServiceError("rate constant must be positive")
        half_life = math.log(2) / rate_constant
        time_unit = intent.units.get("rate_constant_time", "s")
        value = f"{num(half_life)} {time_unit}"
        return verified(
            "Verified first-order half-life",
            (f"k = {inp(rate_constant)} {time_unit}⁻¹",),
            "Half-life, t₁/₂",
            *stated("first_order_half_life"),
            (f"t₁/₂ = {num(math.log(2))} / {inp(rate_constant)}",),
            f"t₁/₂ = {value}",
            value,
        )
    if op == "first_order_concentration":
        initial, rate_constant, time = require_all(intent, "initial", "rate_constant", "time")
        if initial < 0 or rate_constant < 0 or time < 0:
            raise SolveServiceError("concentration, rate constant, and time cannot be negative")
        final = initial * math.exp(-rate_constant * time)
        time_unit = intent.units.get("time", "s")
        value = f"{num(final)} mol/L"
        substitution = f"[A]ₜ = ({inp(initial)})e^(−({inp(rate_constant)})({inp(time)}))"
        return verified(
            "Verified first-order concentration",
            (
                f"[A]₀ = {inp(initial)} mol/L",
                f"k = {inp(rate_constant)} {time_unit}⁻¹",
                f"t = {inp(time)} {time_unit}",
            ),
            "Concentration at time t, [A]ₜ",
            *stated("first_order_concentration"),
            (substitution,),
            f"[A]ₜ = {value}",
            value,
        )
    if op == "arrhenius":
        pre_exponential, activation_energy, temperature = require_all(
            intent, "pre_exponential", "activation_energy", "temperature"
        )
        if pre_exponential <= 0 or activation_energy < 0 or temperature <= 0:
            raise SolveServiceError("Arrhenius inputs must be physically valid")
        rate_constant = pre_exponential * math.exp(-activation_energy / (GAS_R_J * temperature))
        # k has the units of A. A question that gives A without a unit gets a bare number.
        rate_unit = intent.units.get("frequency_factor_time")
        suffix = f" {rate_unit}⁻¹" if rate_unit else ""
        value = f"{num(rate_constant)}{suffix}"
        substitution = (
            f"k = ({inp(pre_exponential)})e^[−{inp(activation_energy)} / "
            f"(({const(GAS_R_J)})({inp(temperature)}))]"
        )
        return verified(
            "Verified Arrhenius rate constant",
            (
                f"A = {inp(pre_exponential)}{suffix}",
                f"Eₐ = {inp(activation_energy / 1000)} kJ/mol ({inp(activation_energy)} J/mol)",
                f"T = {inp(temperature)} K",
            ),
            "Rate constant, k",
            *stated("arrhenius"),
            (substitution,),
            f"k = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported kinetics operation: {op}")


def solve_electrochemistry(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "cell_gibbs":
        electrons, potential = require_all(intent, "electrons", "potential")
        if electrons <= 0:
            raise SolveServiceError("electron count must be positive")
        delta_g_kj = -electrons * FARADAY * potential / 1000
        value = f"{num(delta_g_kj)} kJ/mol"
        substitution = f"ΔG° = −({inp(electrons)})({const(FARADAY)})({inp(potential)}) / 1000"
        return verified(
            "Verified electrochemical free energy",
            (f"n = {inp(electrons)} mol e-", f"E°cell = {inp(potential)} V"),
            "ΔG°",
            *stated("cell_gibbs"),
            (substitution,),
            f"ΔG° = {value}",
            value,
        )
    if op == "nernst":
        standard, electrons, quotient, temperature = require_all(
            intent, "standard_potential", "electrons", "quotient", "temperature"
        )
        if electrons <= 0 or quotient <= 0 or temperature <= 0:
            raise SolveServiceError("Nernst inputs must be positive where required")
        potential = standard - (GAS_R_J * temperature / (electrons * FARADAY)) * math.log(quotient)
        value = f"{num(potential)} V"
        substitution = (
            f"E = {inp(standard)} − [({const(GAS_R_J)})({inp(temperature)}) / "
            f"(({inp(electrons)})({const(FARADAY)}))]ln({inp(quotient)})"
        )
        return verified(
            "Verified cell potential",
            (
                f"E° = {inp(standard)} V",
                f"n = {inp(electrons)}",
                f"Q = {inp(quotient)}",
                f"T = {inp(temperature)} K",
            ),
            "Cell potential, E",
            *stated("nernst"),
            (substitution,),
            f"E = {value}",
            value,
        )
    if op == "electrolysis_mass":
        molar_mass, current, time, electrons = require_all(
            intent, "molar_mass", "current", "time", "electrons"
        )
        if min(molar_mass, current, time, electrons) <= 0:
            raise SolveServiceError("electrolysis inputs must be positive")
        mass = molar_mass * current * time / (electrons * FARADAY)
        value = f"{num(mass)} g"
        substitution = (
            f"m = ({inp(molar_mass)})({inp(current)})({inp(time)}) / "
            f"[({inp(electrons)})({const(FARADAY)})]"
        )
        return verified(
            "Verified electrolysis mass",
            (
                f"M = {inp(molar_mass)} g/mol",
                f"I = {inp(current)} A",
                f"t = {inp(time)} s",
                f"n = {inp(electrons)}",
            ),
            "Deposited mass, m",
            *stated("electrolysis_mass"),
            (substitution,),
            f"m = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported electrochemistry operation: {op}")


def solve_nuclear(intent: ChemistryIntent) -> ChemistryResult:
    initial, elapsed, half_life = require_all(intent, "initial", "elapsed", "half_life")
    if initial < 0 or elapsed < 0 or half_life <= 0:
        raise SolveServiceError("decay inputs must be physically valid")
    remaining = initial * (0.5 ** (elapsed / half_life))
    unit = intent.units.get("initial", "")
    value = f"{num(remaining)}{f' {unit}' if unit else ''}"
    substitution = f"N = {inp(initial)}(1/2)^({inp(elapsed)}/{inp(half_life)})"
    return verified(
        "Verified radioactive decay",
        (
            f"N₀ = {inp(initial)}{f' {unit}' if unit else ''}",
            f"t = {inp(elapsed)} {intent.units.get('time', 's')}",
            f"t₁/₂ = {inp(half_life)} {intent.units.get('time', 's')}",
        ),
        "Remaining amount, N",
        *stated("radioactive_decay"),
        (substitution,),
        f"N = {value}",
        value,
    )
