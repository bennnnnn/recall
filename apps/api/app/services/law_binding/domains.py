"""The values a law's quantities can take, whichever law takes them.

A mass, a resistance, a capacitance, an inductance, a density, a stiffness, a frequency and
an absolute temperature are above zero, and so is a quantity named for what it is (a
period, a wavelength, an amplitude: ``labels``); no body moves faster than light. A
question that states a value outside (a -5 Ω resistor, a gas at -300 °C, a car at
4 x 10^8 m/s) describes nothing a law answers, so the law declines: "A 10 V battery across a
-5 Ω resistor" was verified as -2 A (audit 2026-11-13).

Signed quantities keep their sign: a velocity, a displacement, an acceleration, a charge, a
spring's extension, an angular velocity, and any change (an input written Δ).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache

from app.services.law_binding.fit import variable_kind
from app.services.law_binding.labels import LABELS
from app.services.law_binding.spec import FormulaSpec, VariableSpec, variable_for
from app.services.law_binding.units import dimension_of

_ABOVE_ZERO = frozenset(
    dimension_of(unit)
    for unit in (
        "kilogram",
        "ohm",
        "farad",
        "henry",
        "hertz",
        "kilogram / meter ** 3",
        "newton / meter",
        "kelvin",
    )
)
_SPEED = dimension_of("meter / second")


def outside_domain(spec: FormulaSpec, si_params: Mapping[str, float]) -> str | None:
    """The first of the law's inputs, by name, whose value (in SI) no such quantity takes;
    None when every one is a value it can take."""
    for name, value in si_params.items():
        variable = variable_for(spec, name)
        if variable is None or not variable.visible or _a_change(variable):
            continue
        kind = variable_kind(variable)
        if (kind in _ABOVE_ZERO or _named_quantity(variable)) and value <= 0:
            return name
        if kind == _SPEED and abs(value) > _fastest():
            return name
    return None


def outside_kind(kind: str | None, si_value: float) -> bool:
    """A value of this kind (a dimension, as ``units.dimension_of`` writes it) that no such
    quantity takes: a law solved for a mass is held to a mass's range too. "A force of -10 N
    gives an acceleration of 2 m/s². The mass?" was -5 kg, verified (review 2026-11-13)."""
    if kind in _ABOVE_ZERO and si_value <= 0:
        return True
    return kind == _SPEED and abs(si_value) > _fastest()


@lru_cache(maxsize=1)
def _fastest() -> float:
    """c in m/s, Pint's, with room for a school question's light at 3 x 10^8 m/s, a hair
    over it: 1.2c or 4 x 10^8 m/s is no body's speed."""
    from app.services.units import get_unit_registry

    light = get_unit_registry()("speed_of_light").to_base_units().magnitude
    return float(light) * 1.01


def _a_change(variable: VariableSpec) -> bool:
    return variable.symbol.startswith(("\\Delta", "Δ"))


def _named_quantity(variable: VariableSpec) -> bool:
    """An input the catalog names for a quantity that is a size (a period, a wavelength). One
    that only takes such a value by its words keeps its sign: a spring's extension holds an
    amplitude, and is signed (``labels.holds``)."""
    return variable.name in LABELS
