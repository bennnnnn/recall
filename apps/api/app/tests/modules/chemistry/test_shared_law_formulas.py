"""No chemistry row is a physics law written again: the shared-law test reads formulas.

``test_chemistry_shared_laws`` held chemistry to keep no solver named like a physics law,
and the ideal-gas density sat in both catalogs under other names (audit, 2026-11-25). Each
row's arithmetic is read with its symbols as their dimensions (a pressure, a molar mass, the
gas constant in any units) and evaluated; a chemistry row that computes what a physics law
computes must take that law's arithmetic from ``law_binding.shared_laws``, where its owner's
catalog takes it too.
"""

from __future__ import annotations

import zlib
from collections.abc import Mapping
from dataclasses import replace

import pytest
import sympy

from app.modules.chemistry.formula_laws import FORMULA_LAWS, FormulaLaw
from app.modules.chemistry.gas_density_laws import GAS_DENSITY_LAWS
from app.modules.physics.catalog import CATALOG
from app.services.law_binding.shared_laws import (
    IDEAL_GAS_DENSITY,
    SharedLaw,
    in_names,
    solved_for,
)

# Every law two subjects share (``law_binding.shared_laws``).
SHARED_LAWS = (IDEAL_GAS_DENSITY,)
from app.services.law_binding.spec import FormulaSpec
from app.services.units import get_unit_registry

# The gas constant, in whichever units a row names it.
_GAS_CONSTANT = {"R_atm", "R_J", "R_gas"}
_SALTS = ("a", "b", "c")


def _dimension(unit: str) -> str | None:
    if unit.strip() in {"", "%"}:
        return "dimensionless"
    try:
        quantity = get_unit_registry().parse_expression(unit.replace("·", "*"))
    except Exception:
        return None
    return str(getattr(quantity, "dimensionality", "dimensionless"))


def _signature(
    expression: str, dimensions: Mapping[str, str | None], result: str | None
) -> tuple[object, ...] | None:
    """The law's result dimension, its inputs' dimensions, and its arithmetic's value at a
    few points, each symbol valued by its dimension. A law of pure numbers (a ratio of two
    counts) says nothing of which law it is and has none."""
    used = [dimensions[name] for name in dimensions if name in expression]
    if result is None or None in used or all(dim == "dimensionless" for dim in used):
        return None
    values = _values(expression, dimensions)
    return None if values is None else (result, tuple(sorted(map(str, used))), values)


def _values(expression: str, dimensions: Mapping[str, str | None]) -> tuple[float, ...] | None:
    try:
        tree = sympy.sympify(expression)
    except (sympy.SympifyError, SyntaxError, TypeError):
        return None
    keys: dict[sympy.Symbol, str] = {}
    for symbol in tree.free_symbols:
        name = str(symbol)
        if name in _GAS_CONSTANT:
            keys[symbol] = "gas constant"
        elif name in dimensions:
            dimension = dimensions[name]
            if dimension is None:
                return None
            keys[symbol] = dimension
        else:
            keys[symbol] = name
    values: list[float] = []
    for salt in _SALTS:
        point = {
            symbol: 1.1 + zlib.crc32(f"{key}{salt}".encode()) % 997 / 499
            for symbol, key in keys.items()
        }
        try:
            value = complex(tree.subs(point).evalf())
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        if value.imag or not value.real == value.real:
            return None
        values.append(round(value.real, 9))
    return tuple(values)


def _chemistry(law: FormulaLaw) -> tuple[object, ...] | None:
    dimensions = {name: _dimension(unit) for name, _, unit in law.given}
    return _signature(law.expression, dimensions, _dimension(law.unit))


def _physics(spec: FormulaSpec) -> tuple[object, ...] | None:
    if spec.expression is None or spec.binding is None or len(spec.binding.result) != 1:
        return None
    dimensions = {
        variable.name: "dimensionless"
        if variable.dimensionless
        else _dimension(variable.dimension or "")
        for variable in spec.variables
    }
    return _signature(spec.expression, dimensions, _dimension(spec.binding.result[0]))


def test_no_chemistry_row_is_a_physics_law_written_again() -> None:
    physics: dict[tuple[object, ...], list[str]] = {}
    for spec in CATALOG.values():
        signature = _physics(spec)
        if signature is not None:
            physics.setdefault(signature, []).append(spec.id)
    shared = {law.op for law in SHARED_LAWS}
    copies = {
        (op, physics_op)
        for op, law in FORMULA_LAWS.items()
        if (signature := _chemistry(law)) is not None
        for physics_op in physics.get(signature, [])
    }
    assert {pair for pair in copies if pair[1] not in shared} == set()
    # A row that computes a shared law is one of the rows built from it, never a row that
    # writes its arithmetic again under another name ("density_of_gas", review #2591).
    built = {law.op for law in GAS_DENSITY_LAWS}
    assert {op for op, physics_op in copies if physics_op in shared} <= built
    # The ideal-gas density is found, and is the shared law, not a copy.
    assert ("gas_density", "ideal_gas_density") in copies


def test_a_row_written_again_under_another_name_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    copy = replace(FORMULA_LAWS["gas_density"], op="density_of_gas")
    monkeypatch.setitem(FORMULA_LAWS, "density_of_gas", copy)
    with pytest.raises(AssertionError):
        test_no_chemistry_row_is_a_physics_law_written_again()


@pytest.mark.parametrize("law", SHARED_LAWS, ids=lambda law: law.op)
def test_a_shared_law_is_its_owners_arithmetic(law: SharedLaw) -> None:
    assert law.owner == "physics"
    assert CATALOG[law.op].expression == law.expression


def test_chemistrys_gas_density_rows_read_the_shared_law() -> None:
    names = {"pres": "pressure", "temp": "temperature", "R_gas": "R_atm"}
    gas_law = SHARED_LAWS[0]
    assert FORMULA_LAWS["gas_density"].expression == in_names(gas_law.expression, names)
    assert FORMULA_LAWS["molar_mass_from_density"].expression == solved_for(
        gas_law, "molar_mass", {**names, "ideal_gas_density": "density"}
    )
