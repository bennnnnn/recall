# ruff: noqa: RUF001, RUF002 -- textbook formulas intentionally use multiplication symbols.
"""Chemical amounts, composition, yield, and equation calculations."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.equations import balance_equation, format_balanced
from app.modules.chemistry.formula import parse_formula
from app.modules.chemistry.solvers.common_chem import (
    atomic_mass,
    const,
    inp,
    molar_mass_text,
    molar_mass_working,
    num,
    qty,
    verified,
)
from app.modules.chemistry.solvers.constants import AVOGADRO
from app.modules.chemistry.solvers.params import require
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.species import parse_species
from app.modules.chemistry.stoichiometry import (
    formula_atoms,
    limiting_reagent,
    molar_mass,
    stoichiometry,
)
from app.services.solving import SolveServiceError


def _molar_mass(formula: str) -> float:
    try:
        return molar_mass(formula)
    except ValueError as exc:
        raise SolveServiceError(str(exc)) from exc


def _formula(intent: ChemistryIntent) -> str:
    if not intent.formula:
        raise SolveServiceError("a chemical formula is required")
    return intent.formula


def balanced_text(equation: str) -> str:
    """The balanced equation as text, or a refusal when it does not balance."""
    balanced = balance_equation(equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "equation could not be balanced")
    return format_balanced(balanced)


def _tally_lines(equation: str, *, written: bool = False) -> tuple[str, ...]:
    """One line per element (and one for charge): coefficient × atoms summed on each side.

    ``written`` tallies the coefficients the user typed instead of the balanced ones.
    """
    balanced = balance_equation(equation)
    left_side = balanced.written_reactants if written else balanced.reactants
    right_side = balanced.written_products if written else balanced.products
    parsed = {
        label: parse_species(label, coefficient_already_removed=True)
        for label in (*balanced.reactants, *balanced.products)
    }
    if any(species is None for species in parsed.values()):
        return ()
    elements = list(
        dict.fromkeys(
            element
            for species in parsed.values()
            if species is not None
            for element in species.composition
        )
    )

    def side_text(side: dict[str, int], element: str | None) -> str:
        terms = []
        for label, coefficient in side.items():
            species = parsed[label]
            if species is None:
                continue
            count = species.charge if element is None else species.composition.get(element, 0)
            if count:
                terms.append((coefficient, count))
        total = sum(coefficient * count for coefficient, count in terms)
        shown = " + ".join(f"{coefficient}({count})" for coefficient, count in terms)
        return f"{shown} = {total}" if terms else "0"

    lines = [
        f"{element}: left {side_text(left_side, element)}; right {side_text(right_side, element)}"
        for element in elements
    ]
    if any(species is not None and species.charge for species in parsed.values()):
        lines.append(
            f"charge: left {side_text(left_side, None)}; right {side_text(right_side, None)}"
        )
    return tuple(lines)


def solve_equation(intent: ChemistryIntent) -> ChemistryResult:
    equation = intent.equation
    if not equation:
        raise SolveServiceError("an equation is required")
    balanced = balanced_text(equation)
    if intent.target == "check":
        already = balance_equation(equation).given_balanced
        verdict = (
            f"Yes, it is balanced: {balanced}"
            if already
            else f"No, it is not balanced. Balanced: {balanced}"
        )
        return verified(
            title="Verified balance check",
            given=(f"Equation: {equation}",),
            find="Whether the written coefficients balance",
            formula_name=stated("balance")[0],
            formula=stated("balance")[1],
            substitution=_tally_lines(equation, written=True)
            or (f"Count atoms and charge on each side of: {equation}",),
            answer=verdict,
            value=verdict,
        )
    return verified(
        title="Verified balanced equation",
        given=(f"Unbalanced equation: {equation}",),
        find="Smallest whole-number coefficients",
        formula_name=stated("balance")[0],
        formula=stated("balance")[1],
        substitution=_tally_lines(equation) or (f"Balance element counts: {equation}",),
        answer=balanced,
        value=balanced,
    )


def _mass_terms(formula: str) -> str | None:
    """Each element's atom count times its atomic mass: ``2(1.008) + 1(15.999)``."""
    terms = [
        f"{count}({atomic_mass(known.mass)})"
        for symbol, count in (formula_atoms(formula) or {}).items()
        if (known := BY_SYMBOL.get(symbol)) is not None
    ]
    return " + ".join(terms) or None


def solve_molar_mass(intent: ChemistryIntent) -> ChemistryResult:
    formula = _formula(intent)
    mass = _molar_mass(formula)
    substitution = _mass_terms(formula) or f"RDKit molecular mass for {formula}"
    result = f"{molar_mass_text(mass)} g/mol"
    return verified(
        title="Verified molar mass",
        given=(f"Formula = {formula}",),
        find="Molar mass, M",
        formula_name=stated("molar_mass")[0],
        formula=stated("molar_mass")[1],
        substitution=(f"M = {substitution}",),
        answer=f"M({formula}) = {result}",
        value=result,
    )


def _particles_per_formula(intent: ChemistryIntent, formula: str) -> tuple[int, str]:
    """Atoms per formula unit when the question counts atoms, else 1 particle each."""
    noun = intent.units.get("particle", "particles")
    if noun != "atoms":
        return 1, "particles"
    atoms = formula_atoms(formula)
    if not atoms:
        raise SolveServiceError(f"cannot count the atoms in {formula}")
    return sum(atoms.values()), "atoms"


def solve_amount(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    formula = _formula(intent)
    molar = _molar_mass(formula)
    if op == "mass_to_moles":
        mass = require(intent, "mass", non_negative=True)
        moles = mass / molar
        value = f"{num(moles)} mol"
        return verified(
            "Verified amount of substance",
            (f"mass = {inp(mass)} g", f"M({formula}) = {molar_mass_working(molar)} g/mol"),
            "Amount, n",
            *stated("mass_to_moles"),
            (f"n = {qty(mass, 'g')} / {molar_mass_working(molar)} g/mol",),
            f"n({formula}) = {value}",
            value,
        )
    if op == "moles_to_mass":
        moles = require(intent, "moles", non_negative=True)
        mass = moles * molar
        value = f"{num(mass)} g"
        return verified(
            "Verified mass",
            (f"n = {inp(moles)} mol", f"M({formula}) = {molar_mass_working(molar)} g/mol"),
            "Mass, m",
            *stated("moles_to_mass"),
            (f"m = ({qty(moles, 'mol')})({molar_mass_working(molar)} g/mol)",),
            f"m({formula}) = {value}",
            value,
        )
    per_formula, noun = _particles_per_formula(intent, formula)
    if op == "moles_to_particles":
        moles = require(intent, "moles", non_negative=True)
        particles = moles * AVOGADRO * per_formula
        value = f"{num(particles)} {noun}"
        law_name, base_formula = stated("moles_to_particles")
        particle_formula = (
            base_formula if per_formula == 1 else "N = n Nₐ × (atoms per formula unit)"
        )
        return verified(
            "Verified particle count",
            (f"n = {inp(moles)} mol", f"Nₐ = {const(AVOGADRO)} mol⁻¹"),
            f"Number of {noun}, N",
            law_name,
            particle_formula,
            (
                f"N = ({qty(moles, 'mol')})({const(AVOGADRO)} mol⁻¹)"
                + ("" if per_formula == 1 else f"({per_formula})"),
            ),
            f"N({formula}) = {value}",
            value,
        )
    if op == "particles_to_moles":
        particles = require(intent, "particles", non_negative=True)
        moles = particles / AVOGADRO / per_formula
        value = f"{num(moles)} mol"
        law_name, base_formula = stated("particles_to_moles")
        amount_formula = (
            base_formula if per_formula == 1 else "n = N / (Nₐ × atoms per formula unit)"
        )
        return verified(
            "Verified amount of substance",
            (f"N = {inp(particles)} {noun}", f"Nₐ = {const(AVOGADRO)} mol⁻¹"),
            "Amount, n",
            law_name,
            amount_formula,
            (
                f"n = {inp(particles)} / {const(AVOGADRO)} mol⁻¹"
                + ("" if per_formula == 1 else f" / {per_formula}"),
            ),
            f"n({formula}) = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported amount operation: {op}")


def solve_percent_composition(intent: ChemistryIntent) -> ChemistryResult:
    formula = _formula(intent)
    element = intent.target
    if not element:
        raise SolveServiceError("an element is required")
    atoms = parse_formula(formula)
    count = atoms.get(element)
    known = BY_SYMBOL.get(element)
    if count is None or known is None:
        raise SolveServiceError(f"{element} is not present in {formula}")
    total = _molar_mass(formula)
    percent = count * known.mass / total * 100
    value = f"{num(percent)}%"
    whole = molar_mass_working(total)
    terms = _mass_terms(formula)
    return verified(
        "Verified percent composition",
        (f"Formula = {formula}", f"{element} atoms per formula unit = {count}"),
        f"Mass percent of {element}",
        *stated("percent_composition"),
        (
            f"M({formula}) = {f'{terms} = ' if terms else ''}{whole} g/mol",
            f"% {element} = {count} × {atomic_mass(known.mass)} / {whole} × 100",
        ),
        f"{element} in {formula} = {value}",
        value,
    )


def solve_percent_yield(intent: ChemistryIntent) -> ChemistryResult:
    actual = require(intent, "actual", non_negative=True)
    theoretical = require(intent, "theoretical", positive=True)
    percent = actual / theoretical * 100
    value = f"{num(percent)}%"
    return verified(
        "Verified percent yield",
        (
            f"actual yield = {inp(actual)} g",
            f"theoretical yield = {inp(theoretical)} g",
        ),
        "Percent yield",
        *stated("percent_yield"),
        (f"% yield = ({qty(actual, 'g')} / {qty(theoretical, 'g')}) × 100",),
        f"Percent yield = {value}",
        value,
    )


def solve_stoichiometry(intent: ChemistryIntent) -> ChemistryResult:
    equation = intent.equation
    target = intent.target
    if not equation or not target:
        raise SolveServiceError("equation and target product are required")
    if intent.chemistry_op == "limiting_reagent":
        if len(intent.species) < 2:
            raise SolveServiceError("at least two reactant amounts are required")
        limiting_result = limiting_reagent(equation, intent.species, target)
        if (
            limiting_result.error
            or limiting_result.limiting_reagent is None
            or limiting_result.product_amount is None
        ):
            raise SolveServiceError(limiting_result.error or "limiting reagent solve failed")
        balanced = balance_equation(equation)
        product_coeff = balanced.products[target]
        ratios = tuple(
            f"{name}: {inp(amount)} / {balanced.reactants[name]} = "
            f"{num(amount / balanced.reactants[name])} reaction units"
            for name, amount in intent.species.items()
        )
        value = f"{num(limiting_result.product_amount)} mol {target}"
        limiting_names = " and ".join((limiting_result.limiting_reagent, *limiting_result.tied))
        return verified(
            "Verified limiting reagent",
            tuple(f"n({name}) = {inp(amount)} mol" for name, amount in intent.species.items()),
            f"Limiting reagent and moles of {target}",
            *stated("limiting_reagent"),
            (*ratios, f"n({target}) = smallest reaction units × {product_coeff}"),
            f"Limiting reagent = {limiting_names}; {value}",
            value,
        )
    if len(intent.species) != 1:
        raise SolveServiceError("one known reactant amount is required")
    known, amount = next(iter(intent.species.items()))
    stoich_result = stoichiometry(equation, known, amount, target)
    if stoich_result.error or stoich_result.product_amount is None:
        raise SolveServiceError(stoich_result.error or "stoichiometry solve failed")
    balanced = balance_equation(equation)
    r_coeff = balanced.reactants[known]
    p_coeff = balanced.products[target]
    value = f"{num(stoich_result.product_amount)} mol {target}"
    return verified(
        "Verified stoichiometry",
        (
            f"Balanced equation: {balanced_text(equation)}",
            f"n({known}) = {inp(amount)} mol",
        ),
        f"Moles of {target}",
        stated("stoichiometry")[0],
        f"n({target}) = n({known}) × ({p_coeff} / {r_coeff})",
        (f"n({target}) = {inp(amount)} × ({p_coeff} / {r_coeff})",),
        f"n({target}) = {value}",
        value,
    )
