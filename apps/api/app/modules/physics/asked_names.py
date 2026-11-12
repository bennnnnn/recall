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
The law's own result the glossary has no word for (T, τ, F_e, H_max) is named by that noun
too: a bare letter on **Required** beside "a (acceleration)" on the next reply read as a
gap (review 2026-11-12, D6). Any other symbol the glossary has no meaning for stays
unnamed: no name is better than a wrong one.
"""

from __future__ import annotations

import re
from functools import cache

from app.modules.physics.catalog import formula_spec
from app.modules.physics.glossary import given_meaning
from app.modules.physics.law_nouns import asked_noun
from app.modules.physics.notation import shown
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
    result = _result_dimension(spec, symbol, answer_unit)
    if meaning is None:
        meaning = _result_noun(spec, symbol)
    elif result is None or _dimension(symbol) in {None, result}:
        return meaning
    else:
        meaning = asked_noun(spec)
    return meaning or _result_words().get((symbol, result or "dimensionless"))


# The words for a law's result its glossary and binding leave unnamed, by the symbol as
# the reply shows it and the answer's dimension: T in seconds is a period, in newtons a
# tension; a symbol in another dimension stays unnamed.
_RESULT_WORDS = (
    ("T", "s", "period"),
    ("T", "N", "tension"),
    ("P", "Pa", "pressure"),
    (r"\tau", "N*m", "torque"),
    ("F_e", "N", "electric force"),
    ("F_c", "N", "centripetal force"),
    ("F_b", "N", "buoyant force"),
    ("F_2", "N", "output force"),
    ("F_{min}", "N", "minimum force"),
    ("f", "N", "friction force"),
    ("N", "N", "normal force"),
    ("R", "N", "resultant force"),
    ("f", "Hz", "frequency"),
    ("f'", "Hz", "observed frequency"),
    ("f_b", "Hz", "beat frequency"),
    ("R_s", "ohm", "total resistance"),
    ("R_p", "ohm", "total resistance"),
    (r"|\mathcal{E}|", "V", "induced emf"),
    (r"\mathcal{E}", "V", "induced emf"),
    ("V_{terminal}", "V", "terminal voltage"),
    ("v_f", "m/s", "final velocity"),
    ("v_{impact}", "m/s", "impact speed"),
    ("v_e", "m/s", "escape velocity"),
    ("v_2", "m/s", "speed"),
    ("a_c", "m/s^2", "centripetal acceleration"),
    ("U", "J", "stored energy"),
    ("E_p", "J", "potential energy"),
    (r"\Delta E_k", "J", "change in kinetic energy"),
    (r"\lambda", "m", "wavelength"),
    (r"\lambda_n", "m", "wavelength in the medium"),
    ("I", "N*s", "impulse"),
    ("I", "kg*m^2", "moment of inertia"),
    ("E", "N/C", "electric field"),
    ("B", "T", "magnetic field"),
    (r"t_{\text{top}}", "s", "time to the top"),
    (r"t_{\mathrm{flight}}", "s", "time of flight"),
    (r"H_{\mathrm{max}}", "m", "maximum height"),
    ("H_{max}", "m", "maximum height"),
    (r"\mu", "dimensionless", "coefficient of friction"),
    (r"\eta_C", "dimensionless", "efficiency"),
    (r"\theta_r", "deg", "angle of reflection"),
)


@cache
def _result_words() -> dict[tuple[str, str], str]:
    """``_RESULT_WORDS`` by (symbol, dimension)."""
    return {(symbol, _unit_dimension(unit) or unit): word for symbol, unit, word in _RESULT_WORDS}


# An ask cut from a longer phrase ("to the top", "wavelength in") is no name.
_PART_PHRASE = re.compile(r"^(?:to|in|of|at|on|for|from|by)\b|\b(?:to|in|of|at|on|for|from|by)$")


def _result_noun(spec: FormulaSpec, symbol: str) -> str | None:
    """The law's word for its own result, when ``symbol`` is that result."""
    if symbol not in {spec.result_symbol, shown(spec.result_symbol, spec.id)}:
        return None
    noun = asked_noun(spec)
    return None if noun is None or _PART_PHRASE.search(noun) else noun


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
