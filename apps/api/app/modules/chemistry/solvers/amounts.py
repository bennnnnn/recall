# ruff: noqa: RUF001 -- textbook formulas intentionally use multiplication symbols.
"""Chemical amounts, composition, yield, and equation calculations."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.equations import _parse_formula_atoms, balance_equation
from app.modules.chemistry.solvers.types import ChemistryResult, format_number
from app.modules.chemistry.stoichiometry import (
    PERIODIC_TABLE,
    limiting_reagent,
    molar_mass,
    stoichiometry,
)
from app.services.solving import MathServiceError

AVOGADRO = 6.02214076e23


def _positive(intent: ChemistryIntent, key: str, *, allow_zero: bool = False) -> float:
    try:
        value = intent.params[key]
    except KeyError as exc:
        raise MathServiceError(f"missing chemistry parameter: {key}") from exc
    if value < 0 or (value == 0 and not allow_zero):
        raise MathServiceError(f"{key} must be {'non-negative' if allow_zero else 'positive'}")
    return value


def _formula(intent: ChemistryIntent) -> str:
    if not intent.formula:
        raise MathServiceError("a chemical formula is required")
    return intent.formula


def _balanced_text(equation: str) -> str:
    balanced = balance_equation(equation)
    if not balanced.balanced:
        raise MathServiceError(balanced.error or "equation could not be balanced")
    left = " + ".join(
        f"{coefficient} {species}" if coefficient != 1 else species
        for species, coefficient in balanced.reactants.items()
    )
    right = " + ".join(
        f"{coefficient} {species}" if coefficient != 1 else species
        for species, coefficient in balanced.products.items()
    )
    return f"{left} → {right}"


def solve_equation(intent: ChemistryIntent) -> ChemistryResult:
    equation = intent.equation
    if not equation:
        raise MathServiceError("an equation is required")
    balanced = _balanced_text(equation)
    return ChemistryResult(
        title="Verified balanced equation",
        given=(f"Unbalanced equation: {equation}",),
        find="Smallest whole-number coefficients",
        formula_name="Law of conservation of mass",
        formula="Atoms of each element on reactant side = atoms on product side",
        substitution=(f"Balance element counts: {equation}",),
        answer=balanced,
        answer_value=balanced,
    )


def solve_molar_mass(intent: ChemistryIntent) -> ChemistryResult:
    formula = _formula(intent)
    atoms = _parse_formula_atoms(formula)
    mass = molar_mass(formula)
    terms: list[str] = []
    if atoms:
        for symbol, count in atoms.items():
            info = PERIODIC_TABLE.get(symbol)
            if info is None or not isinstance(info.get("mass"), int | float):
                continue
            terms.append(f"{count}({format_number(float(info['mass']))})")
    substitution = " + ".join(terms) if terms else f"RDKit molecular mass for {formula}"
    result = f"{format_number(mass)} g/mol"
    return ChemistryResult(
        title="Verified molar mass",
        given=(f"Formula = {formula}",),
        find="Molar mass, M",
        formula_name="Molar mass from atomic masses",
        formula="M = Σ(nᵢ × atomic massᵢ)",
        substitution=(f"M = {substitution}",),
        answer=f"M({formula}) = {result}",
        answer_value=result,
    )


def solve_amount(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    formula = _formula(intent)
    molar = molar_mass(formula)
    if op == "mass_to_moles":
        mass = _positive(intent, "mass", allow_zero=True)
        moles = mass / molar
        value = f"{format_number(moles)} mol"
        return ChemistryResult(
            "Verified amount of substance",
            (f"mass = {format_number(mass)} g", f"M({formula}) = {format_number(molar)} g/mol"),
            "Amount, n",
            "Mass–mole relation",
            "n = m / M",
            (f"n = {format_number(mass)} / {format_number(molar)}",),
            f"n({formula}) = {value}",
            value,
        )
    if op == "moles_to_mass":
        moles = _positive(intent, "moles", allow_zero=True)
        mass = moles * molar
        value = f"{format_number(mass)} g"
        return ChemistryResult(
            "Verified mass",
            (f"n = {format_number(moles)} mol", f"M({formula}) = {format_number(molar)} g/mol"),
            "Mass, m",
            "Mass–mole relation",
            "m = nM",
            (f"m = ({format_number(moles)})({format_number(molar)})",),
            f"m({formula}) = {value}",
            value,
        )
    if op == "moles_to_particles":
        moles = _positive(intent, "moles", allow_zero=True)
        particles = moles * AVOGADRO
        value = f"{format_number(particles)} particles"
        return ChemistryResult(
            "Verified particle count",
            (f"n = {format_number(moles)} mol", f"Nₐ = {format_number(AVOGADRO)} mol⁻¹"),
            "Number of particles, N",
            "Avogadro relation",
            "N = nNₐ",
            (f"N = ({format_number(moles)})({format_number(AVOGADRO)})",),
            f"N({formula}) = {value}",
            value,
        )
    if op == "particles_to_moles":
        particles = _positive(intent, "particles", allow_zero=True)
        moles = particles / AVOGADRO
        value = f"{format_number(moles)} mol"
        return ChemistryResult(
            "Verified amount of substance",
            (f"N = {format_number(particles)} particles", f"Nₐ = {format_number(AVOGADRO)} mol⁻¹"),
            "Amount, n",
            "Avogadro relation",
            "n = N / Nₐ",
            (f"n = {format_number(particles)} / {format_number(AVOGADRO)}",),
            f"n({formula}) = {value}",
            value,
        )
    raise MathServiceError(f"unsupported amount operation: {op}")


def solve_percent_composition(intent: ChemistryIntent) -> ChemistryResult:
    formula = _formula(intent)
    element = intent.target
    if not element:
        raise MathServiceError("an element is required")
    atoms = _parse_formula_atoms(formula)
    count = atoms.get(element)
    info = PERIODIC_TABLE.get(element)
    if count is None or info is None or not isinstance(info.get("mass"), int | float):
        raise MathServiceError(f"{element} is not present in {formula}")
    total = molar_mass(formula)
    contribution = count * float(info["mass"])
    percent = contribution / total * 100
    value = f"{format_number(percent)}%"
    return ChemistryResult(
        "Verified percent composition",
        (
            f"Formula = {formula}",
            f"{element} atoms per formula unit = {count}",
            f"M({formula}) = {format_number(total)} g/mol",
        ),
        f"Mass percent of {element}",
        "Percent composition",
        "% element = (mass of element in 1 mol compound / molar mass) × 100",
        (f"% {element} = ({format_number(contribution)} / {format_number(total)}) × 100",),
        f"{element} in {formula} = {value}",
        value,
    )


def solve_percent_yield(intent: ChemistryIntent) -> ChemistryResult:
    actual = _positive(intent, "actual", allow_zero=True)
    theoretical = _positive(intent, "theoretical")
    percent = actual / theoretical * 100
    value = f"{format_number(percent)}%"
    return ChemistryResult(
        "Verified percent yield",
        (
            f"actual yield = {format_number(actual)} g",
            f"theoretical yield = {format_number(theoretical)} g",
        ),
        "Percent yield",
        "Percent yield formula",
        "% yield = (actual yield / theoretical yield) × 100",
        (f"% yield = ({format_number(actual)} / {format_number(theoretical)}) × 100",),
        f"Percent yield = {value}",
        value,
    )


def solve_stoichiometry(intent: ChemistryIntent) -> ChemistryResult:
    equation = intent.equation
    target = intent.target
    if not equation or not target:
        raise MathServiceError("equation and target product are required")
    if intent.chemistry_op == "limiting_reagent":
        if len(intent.species) < 2:
            raise MathServiceError("at least two reactant amounts are required")
        limiting_result = limiting_reagent(equation, intent.species, target)
        if (
            limiting_result.error
            or limiting_result.limiting_reagent is None
            or limiting_result.product_amount is None
        ):
            raise MathServiceError(limiting_result.error or "limiting reagent solve failed")
        balanced = balance_equation(equation)
        product_coeff = balanced.products[target]
        ratios = tuple(
            f"{name}: {format_number(amount)} / {balanced.reactants[name]} = "
            f"{format_number(amount / balanced.reactants[name])} reaction units"
            for name, amount in intent.species.items()
        )
        value = f"{format_number(limiting_result.product_amount)} mol {target}"
        return ChemistryResult(
            "Verified limiting reagent",
            tuple(
                f"n({name}) = {format_number(amount)} mol"
                for name, amount in intent.species.items()
            ),
            f"Limiting reagent and moles of {target}",
            "Stoichiometric limiting-reagent comparison",
            "reaction units = available moles / stoichiometric coefficient",
            (*ratios, f"n({target}) = smallest reaction units × {product_coeff}"),
            f"Limiting reagent = {limiting_result.limiting_reagent}; {value}",
            value,
        )
    if len(intent.species) != 1:
        raise MathServiceError("one known reactant amount is required")
    known, amount = next(iter(intent.species.items()))
    stoich_result = stoichiometry(equation, known, amount, target)
    if stoich_result.error or stoich_result.product_amount is None:
        raise MathServiceError(stoich_result.error or "stoichiometry solve failed")
    balanced = balance_equation(equation)
    r_coeff = balanced.reactants[known]
    p_coeff = balanced.products[target]
    value = f"{format_number(stoich_result.product_amount)} mol {target}"
    return ChemistryResult(
        "Verified stoichiometry",
        (
            f"Balanced equation: {_balanced_text(equation)}",
            f"n({known}) = {format_number(amount)} mol",
        ),
        f"Moles of {target}",
        "Stoichiometric mole ratio",
        f"n({target}) = n({known}) × ({p_coeff} / {r_coeff})",
        (f"n({target}) = {format_number(amount)} × ({p_coeff} / {r_coeff})",),
        f"n({target}) = {value}",
        value,
    )
