# ruff: noqa: RUF001, RUF002 -- textbook formulas intentionally use multiplication symbols.
"""Chemical amounts, composition, yield, and equation calculations."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.equations import _parse_formula_atoms, balance_equation
from app.modules.chemistry.solvers.common_chem import (
    atomic_mass,
    const,
    inp,
    molar_mass_text,
    num,
)
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.species import parse_species
from app.modules.chemistry.stoichiometry import (
    PERIODIC_TABLE,
    limiting_reagent,
    molar_mass,
    stoichiometry,
)
from app.services.solving import SolveServiceError

AVOGADRO = 6.02214076e23


def _positive(intent: ChemistryIntent, key: str, *, allow_zero: bool = False) -> float:
    try:
        value = intent.params[key]
    except KeyError as exc:
        raise SolveServiceError(f"missing chemistry parameter: {key}") from exc
    if value < 0 or (value == 0 and not allow_zero):
        raise SolveServiceError(f"{key} must be {'non-negative' if allow_zero else 'positive'}")
    return value


def _molar_mass(formula: str) -> float:
    try:
        return molar_mass(formula)
    except ValueError as exc:
        raise SolveServiceError(str(exc)) from exc


def _formula(intent: ChemistryIntent) -> str:
    if not intent.formula:
        raise SolveServiceError("a chemical formula is required")
    return intent.formula


def _balanced_text(equation: str) -> str:
    balanced = balance_equation(equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "equation could not be balanced")
    left = " + ".join(
        f"{coefficient} {species}" if coefficient != 1 else species
        for species, coefficient in balanced.reactants.items()
    )
    right = " + ".join(
        f"{coefficient} {species}" if coefficient != 1 else species
        for species, coefficient in balanced.products.items()
    )
    return f"{left} -> {right}"


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
    balanced = _balanced_text(equation)
    if intent.target == "check":
        already = balance_equation(equation).given_balanced
        verdict = (
            f"Yes, it is balanced: {balanced}"
            if already
            else f"No, it is not balanced. Balanced: {balanced}"
        )
        return ChemistryResult(
            title="Verified balance check",
            given=(f"Equation: {equation}",),
            find="Whether the written coefficients balance",
            formula_name="Law of conservation of mass",
            formula="Atoms of each element on reactant side = atoms on product side",
            substitution=_tally_lines(equation, written=True)
            or (f"Count atoms and charge on each side of: {equation}",),
            answer=verdict,
            answer_value=verdict,
        )
    return ChemistryResult(
        title="Verified balanced equation",
        given=(f"Unbalanced equation: {equation}",),
        find="Smallest whole-number coefficients",
        formula_name="Law of conservation of mass",
        formula="Atoms of each element on reactant side = atoms on product side",
        substitution=_tally_lines(equation) or (f"Balance element counts: {equation}",),
        answer=balanced,
        answer_value=balanced,
    )


def solve_molar_mass(intent: ChemistryIntent) -> ChemistryResult:
    formula = _formula(intent)
    atoms = _parse_formula_atoms(formula)
    mass = _molar_mass(formula)
    terms: list[str] = []
    if atoms:
        for symbol, count in atoms.items():
            info = PERIODIC_TABLE.get(symbol)
            if info is None or not isinstance(info.get("mass"), int | float):
                continue
            terms.append(f"{count}({atomic_mass(float(info['mass']))})")
    substitution = " + ".join(terms) if terms else f"RDKit molecular mass for {formula}"
    result = f"{molar_mass_text(mass)} g/mol"
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


def _particles_per_formula(intent: ChemistryIntent, formula: str) -> tuple[int, str]:
    """Atoms per formula unit when the question counts atoms, else 1 particle each."""
    noun = intent.units.get("particle", "particles")
    if noun != "atoms":
        return 1, "particles"
    atoms = _parse_formula_atoms(formula)
    if not atoms:
        raise SolveServiceError(f"cannot count the atoms in {formula}")
    return sum(atoms.values()), "atoms"


def solve_amount(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    formula = _formula(intent)
    molar = _molar_mass(formula)
    if op == "mass_to_moles":
        mass = _positive(intent, "mass", allow_zero=True)
        moles = mass / molar
        value = f"{num(moles)} mol"
        return ChemistryResult(
            "Verified amount of substance",
            (f"mass = {inp(mass)} g", f"M({formula}) = {molar_mass_text(molar)} g/mol"),
            "Amount, n",
            "Mass–mole relation",
            "n = m / M",
            (f"n = {inp(mass)} / {molar_mass_text(molar)}",),
            f"n({formula}) = {value}",
            value,
        )
    if op == "moles_to_mass":
        moles = _positive(intent, "moles", allow_zero=True)
        mass = moles * molar
        value = f"{num(mass)} g"
        return ChemistryResult(
            "Verified mass",
            (f"n = {inp(moles)} mol", f"M({formula}) = {molar_mass_text(molar)} g/mol"),
            "Mass, m",
            "Mass–mole relation",
            "m = nM",
            (f"m = ({inp(moles)})({molar_mass_text(molar)})",),
            f"m({formula}) = {value}",
            value,
        )
    per_formula, noun = _particles_per_formula(intent, formula)
    if op == "moles_to_particles":
        moles = _positive(intent, "moles", allow_zero=True)
        particles = moles * AVOGADRO * per_formula
        value = f"{num(particles)} {noun}"
        return ChemistryResult(
            "Verified particle count",
            (f"n = {inp(moles)} mol", f"Nₐ = {const(AVOGADRO)} mol⁻¹"),
            f"Number of {noun}, N",
            "Avogadro relation",
            "N = nNₐ" if per_formula == 1 else "N = n Nₐ × (atoms per formula unit)",
            (
                f"N = ({inp(moles)})({const(AVOGADRO)})"
                + ("" if per_formula == 1 else f"({per_formula})"),
            ),
            f"N({formula}) = {value}",
            value,
        )
    if op == "particles_to_moles":
        particles = _positive(intent, "particles", allow_zero=True)
        moles = particles / AVOGADRO / per_formula
        value = f"{num(moles)} mol"
        return ChemistryResult(
            "Verified amount of substance",
            (f"N = {inp(particles)} {noun}", f"Nₐ = {const(AVOGADRO)} mol⁻¹"),
            "Amount, n",
            "Avogadro relation",
            "n = N / Nₐ" if per_formula == 1 else "n = N / (Nₐ × atoms per formula unit)",
            (
                f"n = {inp(particles)} / {const(AVOGADRO)}"
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
    atoms = _parse_formula_atoms(formula)
    count = atoms.get(element)
    info = PERIODIC_TABLE.get(element)
    if count is None or info is None or not isinstance(info.get("mass"), int | float):
        raise SolveServiceError(f"{element} is not present in {formula}")
    total = _molar_mass(formula)
    # Rounded like the molar mass so the shown fraction is one convention: 16 / 18.02.
    contribution = round(count * float(info["mass"]), 2)
    percent = contribution / total * 100
    value = f"{num(percent)}%"
    return ChemistryResult(
        "Verified percent composition",
        (
            f"Formula = {formula}",
            f"{element} atoms per formula unit = {count}",
            f"M({formula}) = {molar_mass_text(total)} g/mol",
        ),
        f"Mass percent of {element}",
        "Percent composition",
        "% element = (mass of element in 1 mol compound / molar mass) × 100",
        (f"% {element} = ({molar_mass_text(contribution)} / {molar_mass_text(total)}) × 100",),
        f"{element} in {formula} = {value}",
        value,
    )


def solve_percent_yield(intent: ChemistryIntent) -> ChemistryResult:
    actual = _positive(intent, "actual", allow_zero=True)
    theoretical = _positive(intent, "theoretical")
    percent = actual / theoretical * 100
    value = f"{num(percent)}%"
    return ChemistryResult(
        "Verified percent yield",
        (
            f"actual yield = {inp(actual)} g",
            f"theoretical yield = {inp(theoretical)} g",
        ),
        "Percent yield",
        "Percent yield formula",
        "% yield = (actual yield / theoretical yield) × 100",
        (f"% yield = ({inp(actual)} / {inp(theoretical)}) × 100",),
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
        return ChemistryResult(
            "Verified limiting reagent",
            tuple(f"n({name}) = {inp(amount)} mol" for name, amount in intent.species.items()),
            f"Limiting reagent and moles of {target}",
            "Stoichiometric limiting-reagent comparison",
            "reaction units = available moles / stoichiometric coefficient",
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
    return ChemistryResult(
        "Verified stoichiometry",
        (
            f"Balanced equation: {_balanced_text(equation)}",
            f"n({known}) = {inp(amount)} mol",
        ),
        f"Moles of {target}",
        "Stoichiometric mole ratio",
        f"n({target}) = n({known}) × ({p_coeff} / {r_coeff})",
        (f"n({target}) = {inp(amount)} × ({p_coeff} / {r_coeff})",),
        f"n({target}) = {value}",
        value,
    )
