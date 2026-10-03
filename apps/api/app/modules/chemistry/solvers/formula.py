"""The one solver for every law in ``formula_laws``: evaluate its line, print its rows."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry import sig_figs
from app.modules.chemistry.formula_laws import FORMULA_LAWS
from app.modules.chemistry.given_units import CHEMISTRY_UNITS
from app.modules.chemistry.solvers.common_chem import (
    converted,
    inp,
    molar_mass_working,
    num,
    verified,
)
from app.modules.chemistry.solvers.constants import AVOGADRO, FARADAY, GAS_R
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.law_binding.expression import Notation, evaluate
from app.services.solving import SolveServiceError

# Constants a formula law may name: R in L·atm/(mol·K), Faraday's and Avogadro's constants.
CHEMISTRY_NOTATION = Notation(
    constants={"R_atm": (GAS_R, "R"), "F": (FARADAY, "F"), "N_A": (AVOGADRO, "Nₐ")},
    number=str,
)


# Inputs the element table gives when the question does not state them.
_TABLE_INPUTS = ("molar_mass", "atomic_mass")


def _with_unit(value: str, unit: str) -> str:
    if not unit:
        return value
    return f"{value}{unit}" if unit == "%" else f"{value} {unit}"


class _Given(str):
    """A given as a substitution shows it, "0.500 L"; ``.value`` is the bare number."""

    value: str

    def __new__(cls, value: str, unit: str) -> _Given:
        given = super().__new__(cls, _with_unit(value, unit))
        given.value = value
        return given


def _shown(name: str, value: float) -> str:
    """A given as typed; a molar mass from the table to the table's precision (18.015)."""
    written = sig_figs.current()
    typed = written is not None and repr(value) in written.written
    if not typed and name.startswith(_TABLE_INPUTS):
        return molar_mass_working(value)
    return inp(value)


def convert_quantity(value: float, unit: str, target: str) -> float:
    """A value from one chemistry unit spelling to another, through Pint (K to °C included)."""
    from app.services.units import get_unit_registry

    source, wanted = CHEMISTRY_UNITS.expression(unit), CHEMISTRY_UNITS.expression(target)
    if source is None or wanted is None:
        raise ValueError(f"no conversion from {unit} to {target}")
    quantity = get_unit_registry().Quantity(value, source).to(wanted)
    return float(quantity.magnitude)


def _as_typed(value: float, unit: str, typed_unit: str | None) -> tuple[str, str] | None:
    """The given as the question wrote it (500 mL) and as the law reads it (0.500 L).

    None when no conversion happened, or the law's unit is only another spelling of the typed
    one (0.200 M is 0.200 mol/L). The converted value keeps the figures it was typed with.
    """
    if not typed_unit or not unit or typed_unit == unit:
        return None
    try:
        typed = convert_quantity(value, unit, typed_unit)
    except ValueError:
        return None
    if math.isclose(typed, value, rel_tol=1e-9):
        return None
    written = sig_figs.current()
    literal = None if written is None else written.converted.get(repr(value))
    if literal is None:
        # Undo the round trip's float noise (0.5 L is 500.00000000000006 mL) before echoing.
        return _with_unit(inp(float(f"{typed:.12g}")), typed_unit), inp(value)
    return _with_unit(sig_figs.as_written(literal), typed_unit), converted(value, literal)


def solve_formula_law(intent: ChemistryIntent) -> ChemistryResult:
    law = FORMULA_LAWS.get(intent.chemistry_op)
    if law is None:
        raise SolveServiceError(f"{intent.chemistry_op} is not a formula law")
    values: dict[str, float] = {}
    for name, _label, _unit in law.given:
        value = intent.params.get(name)
        if value is None:
            raise SolveServiceError(f"{law.law_name} needs {name}")
        if value <= 0 and name not in law.signed:
            raise SolveServiceError(f"{name} must be positive")
        values[name] = value
    try:
        result = evaluate(law.expression, values, CHEMISTRY_NOTATION)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise SolveServiceError(f"{law.law_name} has no real answer here") from exc
    shown = _with_unit(num(result), law.unit)
    names = {"formula": intent.formula or "", "target": intent.target or ""}
    units = {name: unit for name, _label, unit in law.given}
    typed = {name: _Given(_shown(name, value), units[name]) for name, value in values.items()}
    given = []
    for name, label, _unit in law.given:
        row = f"{label.format(**names)} = "
        converted = _as_typed(values[name], units[name], intent.units.get(name))
        if converted is not None:
            typed[name] = _Given(converted[1], units[name])
            row = f"{row}{converted[0]} = "
        given.append(f"{row}{typed[name]}")
    return verified(
        f"Verified {law.law_name[0].lower()}{law.law_name[1:]}",
        tuple(given),
        law.find,
        law.law_name,
        law.formula,
        tuple(row.format(**names, **typed) for row in law.substitution),
        f"{law.result.format(**names)} = {shown}",
        shown,
    )
