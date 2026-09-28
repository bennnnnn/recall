"""One verified physics operation: the law, its variables, and its assumptions.

Solvers still own word-problem procedure. This record owns the identity those
procedures used to repeat in the direct-reply dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VariableSpec:
    """One named input of a formula.

    ``dimension`` is a Pint unit expression. A quantity with no dimension sets
    ``dimensionless`` instead of leaving the field blank.
    """

    name: str
    symbol: str
    dimension: str | None = None
    dimensionless: bool = False
    # Classifier flags such as elastic / mode_factor are inputs, not givens.
    visible: bool = True

    def __post_init__(self) -> None:
        if self.dimensionless == (self.dimension is not None):
            raise ValueError(f"{self.name} needs a dimension or an explicit dimensionless flag")


@dataclass(frozen=True, slots=True)
class FormulaVariant:
    """A form of the law that is true only for some of its givens.

    The first variant whose conditions match is the one the reply shows.
    ``latex`` replaces the base equation. ``lines`` replaces it with several
    equations. ``assumptions`` replaces the law's assumptions for that case.
    """

    latex: str | None = None
    lines: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    present: frozenset[str] = frozenset()
    absent: frozenset[str] = frozenset()
    positive: frozenset[str] = frozenset()
    equals: tuple[tuple[str, float], ...] = ()
    # Find-line symbol when this case is the one that matched. None keeps the law's.
    result_symbol: str | None = None


@dataclass(frozen=True, slots=True)
class FormulaSpec:
    """Identity of one ``physics_op``."""

    id: str
    kind: str
    law_name: str
    result_symbol: str
    base_latex: str | None = None
    assumptions: tuple[str, ...] = ()
    variables: tuple[VariableSpec, ...] = ()
    variants: tuple[FormulaVariant, ...] = ()
    # Default assumptions are stated only when every one of these params was given.
    assumptions_require: frozenset[str] = frozenset()
    # Exactly one of these may be absent. That one is the quantity being solved.
    solve_for: tuple[tuple[str, str], ...] = ()


def var(
    name: str,
    symbol: str,
    dimension: str | None = None,
    *,
    dimensionless: bool = False,
    visible: bool = True,
) -> VariableSpec:
    return VariableSpec(
        name=name,
        symbol=symbol,
        dimension=dimension,
        dimensionless=dimensionless,
        visible=visible,
    )


def formula(
    operation: str,
    kind: str,
    law_name: str,
    result_symbol: str,
    base_latex: str | None = None,
    assumptions: tuple[str, ...] = (),
    variables: tuple[VariableSpec, ...] = (),
    variants: tuple[FormulaVariant, ...] = (),
    assumptions_require: frozenset[str] = frozenset(),
    solve_for: tuple[tuple[str, str], ...] = (),
) -> FormulaSpec:
    return FormulaSpec(
        id=operation,
        kind=kind,
        law_name=law_name,
        result_symbol=result_symbol,
        base_latex=base_latex,
        assumptions=assumptions,
        variables=variables,
        variants=variants,
        assumptions_require=assumptions_require,
        solve_for=solve_for,
    )


def matching_variant(spec: FormulaSpec, params: dict[str, float]) -> FormulaVariant | None:
    """The first variant whose givens match, if any."""
    for variant in spec.variants:
        if _variant_matches(variant, params):
            return variant
    return None


def _variant_matches(variant: FormulaVariant, params: dict[str, float]) -> bool:
    if not variant.present <= params.keys():
        return False
    if variant.absent & params.keys():
        return False
    if any(params.get(name, 0.0) <= 0 for name in variant.positive):
        return False
    return all(params.get(name) == value for name, value in variant.equals)


def select_formula(
    spec: FormulaSpec, params: dict[str, float]
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    """Base equation, extra equation lines, and the assumptions that apply."""
    variant = matching_variant(spec, params)
    if variant is not None:
        latex = spec.base_latex if variant.latex is None else variant.latex
        return latex, variant.lines, variant.assumptions
    assumptions = spec.assumptions
    if spec.assumptions_require and not spec.assumptions_require <= params.keys():
        assumptions = ()
    return spec.base_latex, (), assumptions


def visible_assumptions(spec: FormulaSpec, params: dict[str, float]) -> tuple[str, ...]:
    """Assumptions that are true for this solve, not merely printed on the law."""
    return select_formula(spec, params)[2]


def variable_for(spec: FormulaSpec, name: str) -> VariableSpec | None:
    """The declared input with this parameter name, or nothing."""
    for variable in spec.variables:
        if variable.name == name:
            return variable
    return None


def symbol_for(spec: FormulaSpec, name: str) -> str | None:
    """Display symbol declared for this operation, or nothing."""
    variable = variable_for(spec, name)
    return None if variable is None else variable.symbol
