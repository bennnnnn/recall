"""What the asked quantity is called on a worked reply's **Required** line.

The glossary names a given by its catalog name, which a law owns. The asked quantity is
known only by its symbol, and a symbol means different things in different laws: R is a
resistance in Ohm's law and a range in projectile motion, Q a charge, a heat or a flow rate,
W work or weight, V a voltage or a volume, I a current, an intensity or a moment of inertia.
Read by its letter alone, "find the heat to warm 2 kg of water" was answered under
"Required: Q (charge)", and a projectile's range under "R (resistance)".

So the symbol is named, in order, by:
- the law's own variable written with it (a law that solves for one of its inputs);
- the letter's usual meaning, only when its unit is the result's (the law's binding, or
  the verified answer's unit when the law has none);
- otherwise the noun the law's binding asks it with ("range", "weight", "moment of inertia").
A symbol the glossary has no meaning for stays unnamed, as before: no name is better than a
wrong one.
"""

from __future__ import annotations

from app.modules.physics.catalog import formula_spec
from app.modules.physics.glossary import given_meaning
from app.modules.physics.law_nouns import asked_noun
from app.modules.physics.solvers.si import PARAM_SI_DIMENSIONS
from app.services.law_binding.spec import FormulaSpec
from app.services.law_binding.units import unit_dimension


def asked_meaning(operation: str, symbol: str, answer_unit: str | None = None) -> str | None:
    """What ``symbol``, the quantity a reply finds by law ``operation``, stands for."""
    spec = formula_spec(operation)
    kind = spec.kind if spec is not None else ""
    if spec is None:
        return given_meaning(operation, kind, symbol)
    own = _own_variable(spec, symbol)
    if own is not None:
        return given_meaning(operation, kind, own)
    meaning = given_meaning(operation, kind, symbol)
    if meaning is None:
        return None
    result = _result_dimension(spec, symbol, answer_unit)
    if result is None or _dimension(symbol) in {None, result}:
        return meaning
    return asked_noun(spec)


def _own_variable(spec: FormulaSpec, symbol: str) -> str | None:
    """The catalog name of the law's input written as ``symbol``: a quantity it solves for,
    or an input whose name is not its symbol."""
    for name, written in spec.solve_for:
        if written == symbol:
            return name
    for variable in spec.variables:
        if variable.symbol == symbol and variable.name != symbol:
            return variable.name
    return None


def _dimension(name: str) -> str | None:
    unit = PARAM_SI_DIMENSIONS.get(name)
    return None if unit is None else _unit_dimension(unit)


def _result_dimension(spec: FormulaSpec, symbol: str, answer_unit: str | None) -> str | None:
    """The asked quantity's dimension: the binding's result unit when it asks the law's own
    result, else the verified answer's unit (a law solved for another of its quantities)."""
    if symbol == spec.result_symbol and spec.binding is not None and spec.binding.result:
        return _unit_dimension(spec.binding.result[0])
    return None if not answer_unit else _unit_dimension(answer_unit)


def _unit_dimension(unit: str) -> str | None:
    if unit == "dimensionless":
        return unit
    reading = unit_dimension(unit)
    return None if reading is None else reading[0]
