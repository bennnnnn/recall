"""The one solver for every law in ``formula_laws``: evaluate its line, print its rows."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry import sig_figs
from app.modules.chemistry.formula_laws import FORMULA_LAWS
from app.modules.chemistry.solvers.common_chem import inp, molar_mass_working, num, verified
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


def _shown(name: str, value: float) -> str:
    """A given as typed; a molar mass from the table to the table's precision (18.015)."""
    written = sig_figs.current()
    typed = written is not None and repr(value) in written.written
    if not typed and name.startswith(_TABLE_INPUTS):
        return molar_mass_working(value)
    return inp(value)


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
    typed = {name: _shown(name, value) for name, value in values.items()}
    return verified(
        f"Verified {law.law_name[0].lower()}{law.law_name[1:]}",
        tuple(
            _with_unit(f"{label.format(**names)} = {typed[name]}", unit)
            for name, label, unit in law.given
        ),
        law.find,
        law.law_name,
        law.formula,
        tuple(row.format(**names, **typed) for row in law.substitution),
        f"{law.result.format(**names)} = {shown}",
        shown,
    )
