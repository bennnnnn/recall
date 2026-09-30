# ruff: noqa: RUF001 -- textbook formulas intentionally use Unicode math notation.
"""Thermochemistry, equilibrium, kinetics, electrochemistry, and nuclear solves."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers.types import ChemistryResult, format_number
from app.services.solving import SolveServiceError

GAS_R_J = 8.31446261815324
FARADAY = 96485.33212


def _required(intent: ChemistryIntent, *keys: str) -> list[float]:
    values: list[float] = []
    for key in keys:
        try:
            values.append(intent.params[key])
        except KeyError as exc:
            raise SolveServiceError(f"missing chemistry parameter: {key}") from exc
    return values


def solve_thermochemistry(intent: ChemistryIntent) -> ChemistryResult:
    if intent.chemistry_op == "heat":
        mass, specific_heat, delta_t = _required(intent, "mass", "specific_heat", "delta_t")
        if mass <= 0 or specific_heat <= 0:
            raise SolveServiceError("mass and specific heat must be positive")
        heat_j = mass * specific_heat * delta_t
        value = f"{format_number(heat_j)} J"
        substitution = (
            f"q = ({format_number(mass)})({format_number(specific_heat)})({format_number(delta_t)})"
        )
        return ChemistryResult(
            "Verified heat calculation",
            (
                f"m = {format_number(mass)} g",
                f"c = {format_number(specific_heat)} J/(g·°C)",
                f"ΔT = {format_number(delta_t)} °C",
            ),
            "Heat transferred, q",
            "Specific-heat equation",
            "q = mcΔT",
            (substitution,),
            f"q = {value}",
            value,
        )
    if intent.chemistry_op == "gibbs":
        delta_h, delta_s, temperature = _required(intent, "delta_h", "delta_s", "temperature")
        if temperature <= 0:
            raise SolveServiceError("temperature must be positive Kelvin")
        # Extractors normalize both H and S to kJ-based units.
        delta_g = delta_h - temperature * delta_s
        value = f"{format_number(delta_g)} kJ/mol"
        substitution = (
            f"ΔG = {format_number(delta_h)} − ({format_number(temperature)})"
            f"({format_number(delta_s)})"
        )
        return ChemistryResult(
            "Verified Gibbs free energy",
            (
                f"ΔH = {format_number(delta_h)} kJ/mol",
                f"ΔS = {format_number(delta_s)} kJ/(mol·K)",
                f"T = {format_number(temperature)} K",
            ),
            "Gibbs free-energy change, ΔG",
            "Gibbs equation",
            "ΔG = ΔH − TΔS",
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


def _equilibrium_expression(
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
        if product:
            numerator *= concentration**coefficient
            numerator_terms.append(f"{label}^{coefficient}")
            substitutions_top.append(f"({format_number(concentration)})^{coefficient}")
        else:
            denominator *= concentration**coefficient
            denominator_terms.append(f"{label}^{coefficient}")
            substitutions_bottom.append(f"({format_number(concentration)})^{coefficient}")

    for species, coefficient in balanced.products.items():
        _accumulate(species, coefficient, product=True)
    for species, coefficient in balanced.reactants.items():
        _accumulate(species, coefficient, product=False)
    if not numerator_terms and not denominator_terms:
        raise SolveServiceError("the equilibrium expression has no concentration terms")
    top = " × ".join(numerator_terms) if numerator_terms else "1"
    bottom = " × ".join(denominator_terms) if denominator_terms else "1"
    top_sub = " × ".join(substitutions_top) if substitutions_top else "1"
    bottom_sub = " × ".join(substitutions_bottom) if substitutions_bottom else "1"
    return numerator / denominator, f"({top}) / ({bottom})", f"({top_sub}) / ({bottom_sub})"


def solve_equilibrium(intent: ChemistryIntent) -> ChemistryResult:
    value_num, expression, substitution = _equilibrium_expression(intent)
    symbol = "Kc" if intent.chemistry_op == "equilibrium_constant" else "Qc"
    title = "Verified equilibrium constant" if symbol == "Kc" else "Verified reaction quotient"
    value = format_number(value_num)
    return ChemistryResult(
        title,
        tuple(
            f"[{species}] = {format_number(concentration)} mol/L"
            for species, concentration in intent.species.items()
        ),
        symbol,
        "Law of mass action",
        f"{symbol} = {expression}",
        (f"{symbol} = {substitution}",),
        f"{symbol} = {value}",
        value,
    )


def solve_kinetics(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "first_order_half_life":
        (rate_constant,) = _required(intent, "rate_constant")
        if rate_constant <= 0:
            raise SolveServiceError("rate constant must be positive")
        half_life = math.log(2) / rate_constant
        time_unit = intent.units.get("rate_constant_time", "s")
        value = f"{format_number(half_life)} {time_unit}"
        return ChemistryResult(
            "Verified first-order half-life",
            (f"k = {format_number(rate_constant)} {time_unit}⁻¹",),
            "Half-life, t₁/₂",
            "First-order half-life",
            "t₁/₂ = ln(2) / k",
            (f"t₁/₂ = {format_number(math.log(2))} / {format_number(rate_constant)}",),
            f"t₁/₂ = {value}",
            value,
        )
    if op == "first_order_concentration":
        initial, rate_constant, time = _required(intent, "initial", "rate_constant", "time")
        if initial < 0 or rate_constant < 0 or time < 0:
            raise SolveServiceError("concentration, rate constant, and time cannot be negative")
        final = initial * math.exp(-rate_constant * time)
        time_unit = intent.units.get("time", "s")
        value = f"{format_number(final)} mol/L"
        substitution = (
            f"[A]ₜ = ({format_number(initial)})e^(−{format_number(rate_constant)}"
            f" × {format_number(time)})"
        )
        return ChemistryResult(
            "Verified first-order concentration",
            (
                f"[A]₀ = {format_number(initial)} mol/L",
                f"k = {format_number(rate_constant)} {time_unit}⁻¹",
                f"t = {format_number(time)} {time_unit}",
            ),
            "Concentration at time t, [A]ₜ",
            "Integrated first-order rate law",
            "[A]ₜ = [A]₀e⁻ᵏᵗ",
            (substitution,),
            f"[A]ₜ = {value}",
            value,
        )
    if op == "arrhenius":
        pre_exponential, activation_energy, temperature = _required(
            intent, "pre_exponential", "activation_energy", "temperature"
        )
        if pre_exponential <= 0 or activation_energy < 0 or temperature <= 0:
            raise SolveServiceError("Arrhenius inputs must be physically valid")
        rate_constant = pre_exponential * math.exp(-activation_energy / (GAS_R_J * temperature))
        # k has the units of A. A question that gives A without a unit gets a bare number.
        rate_unit = intent.units.get("frequency_factor_time")
        suffix = f" {rate_unit}⁻¹" if rate_unit else ""
        value = f"{format_number(rate_constant)}{suffix}"
        substitution = (
            f"k = ({format_number(pre_exponential)})e^[−{format_number(activation_energy)} / "
            f"({format_number(GAS_R_J)} × {format_number(temperature)})]"
        )
        return ChemistryResult(
            "Verified Arrhenius rate constant",
            (
                f"A = {format_number(pre_exponential)}{suffix}",
                f"Eₐ = {format_number(activation_energy / 1000)} kJ/mol",
                f"T = {format_number(temperature)} K",
            ),
            "Rate constant, k",
            "Arrhenius equation",
            "k = Ae^(−Eₐ/RT)",
            (substitution,),
            f"k = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported kinetics operation: {op}")


def solve_electrochemistry(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "cell_gibbs":
        electrons, potential = _required(intent, "electrons", "potential")
        if electrons <= 0:
            raise SolveServiceError("electron count must be positive")
        delta_g_kj = -electrons * FARADAY * potential / 1000
        value = f"{format_number(delta_g_kj)} kJ/mol"
        substitution = (
            f"ΔG° = −({format_number(electrons)})({format_number(FARADAY)})"
            f"({format_number(potential)}) / 1000"
        )
        return ChemistryResult(
            "Verified electrochemical free energy",
            (f"n = {format_number(electrons)} mol e⁻", f"E°cell = {format_number(potential)} V"),
            "ΔG°",
            "Electrochemical Gibbs relation",
            "ΔG° = −nFE°cell",
            (substitution,),
            f"ΔG° = {value}",
            value,
        )
    if op == "nernst":
        standard, electrons, quotient, temperature = _required(
            intent, "standard_potential", "electrons", "quotient", "temperature"
        )
        if electrons <= 0 or quotient <= 0 or temperature <= 0:
            raise SolveServiceError("Nernst inputs must be positive where required")
        potential = standard - (GAS_R_J * temperature / (electrons * FARADAY)) * math.log(quotient)
        value = f"{format_number(potential)} V"
        substitution = (
            f"E = {format_number(standard)} − [({format_number(GAS_R_J)})"
            f"({format_number(temperature)}) / ({format_number(electrons)} × "
            f"{format_number(FARADAY)})]ln({format_number(quotient)})"
        )
        return ChemistryResult(
            "Verified cell potential",
            (
                f"E° = {format_number(standard)} V",
                f"n = {format_number(electrons)}",
                f"Q = {format_number(quotient)}",
                f"T = {format_number(temperature)} K",
            ),
            "Cell potential, E",
            "Nernst equation",
            "E = E° − (RT/nF)ln Q",
            (substitution,),
            f"E = {value}",
            value,
        )
    if op == "electrolysis_mass":
        molar_mass, current, time, electrons = _required(
            intent, "molar_mass", "current", "time", "electrons"
        )
        if min(molar_mass, current, time, electrons) <= 0:
            raise SolveServiceError("electrolysis inputs must be positive")
        mass = molar_mass * current * time / (electrons * FARADAY)
        value = f"{format_number(mass)} g"
        substitution = (
            f"m = ({format_number(molar_mass)})({format_number(current)})"
            f"({format_number(time)}) / [({format_number(electrons)})"
            f"({format_number(FARADAY)})]"
        )
        return ChemistryResult(
            "Verified electrolysis mass",
            (
                f"M = {format_number(molar_mass)} g/mol",
                f"I = {format_number(current)} A",
                f"t = {format_number(time)} s",
                f"n = {format_number(electrons)}",
            ),
            "Deposited mass, m",
            "Faraday's law of electrolysis",
            "m = MIt / nF",
            (substitution,),
            f"m = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported electrochemistry operation: {op}")


def solve_nuclear(intent: ChemistryIntent) -> ChemistryResult:
    initial, elapsed, half_life = _required(intent, "initial", "elapsed", "half_life")
    if initial < 0 or elapsed < 0 or half_life <= 0:
        raise SolveServiceError("decay inputs must be physically valid")
    remaining = initial * (0.5 ** (elapsed / half_life))
    unit = intent.units.get("initial", "")
    value = f"{format_number(remaining)}{f' {unit}' if unit else ''}"
    substitution = (
        f"N = {format_number(initial)}(1/2)^({format_number(elapsed)}/{format_number(half_life)})"
    )
    return ChemistryResult(
        "Verified radioactive decay",
        (
            f"N₀ = {format_number(initial)}{f' {unit}' if unit else ''}",
            f"t = {format_number(elapsed)} {intent.units.get('time', 's')}",
            f"t₁/₂ = {format_number(half_life)} {intent.units.get('time', 's')}",
        ),
        "Remaining amount, N",
        "Radioactive decay law",
        "N = N₀(1/2)^(t/t₁/₂)",
        (substitution,),
        f"N = {value}",
        value,
    )
