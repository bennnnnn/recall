# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Composition formulas and multi-step stoichiometry."""

from __future__ import annotations

from dataclasses import replace

from app.models.schemas.chemistry import ChemistryIntent
from app.models.schemas.chemistry.scene import StoichScene, StoichStep
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.solvers.amounts import AVOGADRO, _balanced_text
from app.modules.chemistry.solvers.common_chem import num, verified
from app.modules.chemistry.solvers.solutions import GAS_R
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.stoichiometry import molar_mass
from app.services.solving import MathServiceError


def _formula_from_counts(counts: dict[str, int]) -> str:
    return "".join(
        element if count == 1 else f"{element}{count}" for element, count in counts.items() if count
    )


def _integer_ratio(ratios: dict[str, float]) -> dict[str, int] | None:
    for multiplier in range(1, 9):
        scaled = {element: ratio * multiplier for element, ratio in ratios.items()}
        if all(abs(value - round(value)) <= 0.1 for value in scaled.values()):
            return {element: int(round(value)) for element, value in scaled.items()}
    return None


def _empirical_counts(percents: dict[str, float]) -> dict[str, int]:
    if not percents or any(value <= 0 for value in percents.values()):
        raise MathServiceError("percent composition must be positive")
    if abs(sum(percents.values()) - 100) > 1.5:
        raise MathServiceError("percentages must add to about 100")
    moles: dict[str, float] = {}
    for element, percent in percents.items():
        try:
            moles[element] = percent / molar_mass(element)
        except ValueError as exc:
            raise MathServiceError(f"unknown element {element}") from exc
    smallest = min(moles.values())
    ratios = {element: value / smallest for element, value in moles.items()}
    counts = _integer_ratio(ratios)
    if counts is None:
        raise MathServiceError("percentages do not form a simple integer ratio")
    return counts


def solve_empirical(intent: ChemistryIntent) -> ChemistryResult:
    counts = _empirical_counts(dict(intent.species))
    formula = _formula_from_counts(counts)
    given = tuple(f"{element} = {num(percent)}%" for element, percent in intent.species.items())
    return verified(
        "Verified empirical formula",
        given,
        "Empirical formula",
        "Empirical formula from percent composition",
        "percent → grams → moles → divide by smallest → integer ratio",
        tuple(f"n({element}) ratio → {count}" for element, count in counts.items()),
        formula,
        formula,
    )


def solve_molecular(intent: ChemistryIntent) -> ChemistryResult:
    molar = intent.params.get("molar_mass")
    if molar is None or molar <= 0:
        raise MathServiceError("molecular molar mass must be positive")
    counts = _empirical_counts(dict(intent.species))
    empirical = _formula_from_counts(counts)
    empirical_mass = molar_mass(empirical)
    multiple = molar / empirical_mass
    if abs(multiple - round(multiple)) > 0.05:
        raise MathServiceError("molar mass is not an integer multiple of the empirical mass")
    factor = int(round(multiple))
    molecular_counts = {element: count * factor for element, count in counts.items()}
    formula = _formula_from_counts(molecular_counts)
    return verified(
        "Verified molecular formula",
        (
            *[f"{element} = {num(percent)}%" for element, percent in intent.species.items()],
            f"M = {num(molar)} g/mol",
        ),
        "Molecular formula",
        "Molecular formula from the empirical formula",
        "n = M_molecular / M_empirical",
        (
            f"empirical formula = {empirical}",
            f"n = {num(molar)} / {num(empirical_mass)} = {factor}",
        ),
        formula,
        formula,
    )


def _to_moles(
    formula: str,
    amount: float,
    unit: str,
    params: dict[str, float],
) -> float:
    if amount < 0:
        raise MathServiceError("amount cannot be negative")
    if unit == "mol":
        return amount
    if unit == "g":
        return amount / molar_mass(formula)
    if unit == "particles":
        return amount / AVOGADRO
    if unit == "L":
        pressure = params.get("pressure")
        temperature = params.get("temperature")
        if pressure is None or temperature is None or pressure <= 0 or temperature <= 0:
            raise MathServiceError("gas amount needs positive pressure and temperature")
        return pressure * amount / (GAS_R * temperature)
    if unit == "solution":
        molarity = params.get("molarity")
        if molarity is None or molarity < 0:
            raise MathServiceError("solution amount needs molarity")
        return molarity * amount
    raise MathServiceError(f"unsupported amount unit {unit}")


def _from_moles(
    formula: str, moles: float, unit: str, params: dict[str, float]
) -> tuple[float, str]:
    if unit == "mol":
        return moles, "mol"
    if unit == "g":
        return moles * molar_mass(formula), "g"
    if unit == "particles":
        return moles * AVOGADRO, "particles"
    if unit == "L":
        pressure = params.get("pressure")
        temperature = params.get("temperature")
        if pressure is None or temperature is None or pressure <= 0 or temperature <= 0:
            raise MathServiceError("gas volume needs positive pressure and temperature")
        return moles * GAS_R * temperature / pressure, "L"
    raise MathServiceError(f"unsupported result unit {unit}")


def _ratio(intent: ChemistryIntent) -> tuple[str, str, int, int, str]:
    equation = intent.equation
    target = intent.target
    if not equation or not target or len(intent.species) != 1:
        raise MathServiceError("one reactant, an equation, and a product are required")
    known = next(iter(intent.species))
    balanced = balance_equation(equation)
    if not balanced.balanced:
        raise MathServiceError(balanced.error or "equation could not be balanced")
    if known not in balanced.reactants or target not in balanced.products:
        raise MathServiceError("reactant or product is not in the balanced equation")
    return known, target, balanced.reactants[known], balanced.products[target], equation


def solve_mass_stoichiometry(intent: ChemistryIntent) -> ChemistryResult:
    known, target, reactant_coeff, product_coeff, equation = _ratio(intent)
    known_unit = intent.units.get("known", "g")
    find_unit = intent.units.get("find", "g")
    amount = next(iter(intent.species.values()))
    moles = _to_moles(known, amount, known_unit, intent.params)
    product_moles = moles * product_coeff / reactant_coeff
    value_num, unit = _from_moles(target, product_moles, find_unit, intent.params)
    value = f"{num(value_num)} {unit}"
    known_moles = f"{num(moles)} mol"
    product_ratio = f"{num(moles)} × ({product_coeff} / {reactant_coeff})"
    result = verified(
        "Verified stoichiometry chain",
        (
            f"Balanced equation: {_balanced_text(equation)}",
            f"{known} = {num(amount)} {known_unit}",
        ),
        f"Amount of {target}",
        "Mass–mole–particle stoichiometry",
        f"n({target}) = n({known}) × ({product_coeff} / {reactant_coeff})",
        (
            f"n({known}) = {known_moles}",
            f"n({target}) = {product_ratio}",
        ),
        f"{target} = {value}",
        value,
    )
    return replace(
        result,
        scene=StoichScene(
            title="Stoichiometry chain",
            steps=[
                StoichStep(label=f"n({known})", value=known_moles),
                StoichStep(label=f"n({target})", value=product_ratio),
                StoichStep(label=target, value=value),
            ],
        ),
    )


def solve_solution_stoichiometry(intent: ChemistryIntent) -> ChemistryResult:
    return solve_mass_stoichiometry(intent)


def solve_gas_stoichiometry(intent: ChemistryIntent) -> ChemistryResult:
    return solve_mass_stoichiometry(intent)


def solve_limiting_amounts(intent: ChemistryIntent, *, unit: str) -> ChemistryResult:
    equation = intent.equation
    target = intent.target
    if not equation or not target or len(intent.species) < 2:
        raise MathServiceError("two reactant amounts, an equation, and a product are required")
    balanced = balance_equation(equation)
    if not balanced.balanced or target not in balanced.products:
        raise MathServiceError("equation could not be balanced for that product")
    moles: dict[str, float] = {}
    for formula, amount in intent.species.items():
        if formula not in balanced.reactants:
            raise MathServiceError(f"{formula} is not a reactant")
        params = dict(intent.params)
        if unit == "solution":
            molarity = intent.params.get(formula)
            if molarity is None:
                raise MathServiceError(f"missing molarity for {formula}")
            params["molarity"] = molarity
        moles[formula] = _to_moles(formula, amount, unit, params)
    product_coeff = balanced.products[target]
    best_name = ""
    best_units = float("inf")
    for formula, amount in moles.items():
        units = amount / balanced.reactants[formula]
        if units < best_units:
            best_units = units
            best_name = formula
    product_moles = best_units * product_coeff
    product_mass = product_moles * molar_mass(target)
    excess_lines = []
    for formula, amount in moles.items():
        if formula == best_name:
            continue
        used = best_units * balanced.reactants[formula]
        leftover = amount - used
        if unit == "g":
            excess_lines.append(f"excess {formula} = {num(leftover * molar_mass(formula))} g")
        else:
            excess_lines.append(f"excess {formula} = {num(leftover)} mol")
    value = f"{num(product_mass)} g {target}"
    if unit == "solution":
        given = tuple(
            f"{formula} = {num(amount)} L at {num(intent.params[formula])} M"
            for formula, amount in intent.species.items()
        )
    else:
        given = tuple(
            f"{formula} = {num(amount)} {unit}" for formula, amount in intent.species.items()
        )
    return verified(
        "Verified limiting reagent",
        given,
        f"Limiting reagent, theoretical yield of {target}, and excess",
        "Limiting reagent from amounts",
        "reaction units = available moles / coefficient",
        (
            f"limiting reagent = {best_name}",
            f"n({target}) = {num(product_moles)} mol",
            *excess_lines,
        ),
        f"Limiting reagent = {best_name}; {value}",
        value,
    )


def solve_limiting_mass(intent: ChemistryIntent) -> ChemistryResult:
    return solve_limiting_amounts(intent, unit="g")


def solve_limiting_solution(intent: ChemistryIntent) -> ChemistryResult:
    return solve_limiting_amounts(intent, unit="solution")
