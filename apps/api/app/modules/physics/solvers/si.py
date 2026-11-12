"""Givens in SI: the catalog's dimension for each, Pint's conversion, g, and the one unknown."""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from pint.errors import PintError

from app.modules.physics.bodies import SCHOOL_GRAVITY
from app.modules.physics.schemas import PhysicsIntent
from app.services.law_binding.spec import FormulaSpec
from app.services.solving import SolveServiceError


def _dimensions_from_catalog() -> dict[str, str]:
    """SI dimension of every declared variable. The catalog is the only list."""
    from app.modules.physics.catalog import CATALOG, result_variable

    dims: dict[str, str] = {}
    for spec in CATALOG.values():
        # A law's result is an input when the law is solved for another of its quantities.
        stated = result_variable(spec)
        for variable in (*spec.variables, *((stated,) if stated else ())):
            dimension = "dimensionless" if variable.dimensionless else variable.dimension
            if not dimension:
                raise RuntimeError(f"{spec.id}.{variable.name} has no dimension")
            previous = dims.get(variable.name)
            if previous is not None and previous != dimension:
                raise RuntimeError(
                    f"{variable.name} is {previous!r} and {dimension!r} on {spec.id}"
                )
            dims[variable.name] = dimension
    return dims


PARAM_SI_DIMENSIONS: dict[str, str] = _dimensions_from_catalog()


# Words that count rather than measure: a dimensionless input written with one.
_COUNT_UNITS = frozenset(
    {
        "turns",
        "turn",
        "lines",
        "nuclei",
        "atoms",
        "microstates",
        "oscillations",
        "oscillation",
        "vibrations",
        "cycles",
        "swings",
    }
)


# Units whose zero is not zero. These must be constructed as a Quantity rather
# than multiplied, and a *difference* in them is not the same as a value: a
# rise of 50 °C is 50 K, not 323.15 K. A `delta_` input is a difference.
_OFFSET_UNITS = frozenset({"degC", "degF", "celsius", "fahrenheit"})


_OFFSET_DIFFERENCES = {
    "degC": "delta_degC",
    "celsius": "delta_degC",
    "degF": "delta_degF",
    "fahrenheit": "delta_degF",
}


def one_unknown(params: dict[str, float], keys: tuple[str, ...]) -> str:
    """The one key of ``keys`` the params leave out; any other count is refused."""
    missing = [key for key in keys if key not in params]
    if len(missing) != 1:
        raise SolveServiceError("needs exactly one unknown")
    return missing[0]


def gravity_of(params: dict[str, float]) -> float:
    """The g a solver uses: the one in the intent, or Earth's school value."""
    return params["g"] if "g" in params else SCHOOL_GRAVITY["earth"]


def to_si(value: float, unit: str, *, expected_key: str | None = None) -> float:
    """Convert a value with a unit string to its SI base using Pint.

    Returns the value unchanged if the unit is empty (assumed already SI).
    Raises when ``expected_key`` has a known dimension and the unit does not match.
    """
    if not unit:
        return value
    scale, offset_reading = _si_conversion(unit, expected_key)
    if offset_reading is None:
        return value * scale
    from app.services.units import get_unit_registry

    # Celsius is an offset unit, not a scale factor: `value * ureg("degC")` raises
    # OffsetUnitCalculusError rather than converting.
    quantity = get_unit_registry().Quantity(value, offset_reading)
    return float(quantity.to_base_units().magnitude)


@lru_cache(maxsize=2048)
def _si_conversion(unit: str, expected_key: str | None) -> tuple[float, str | None]:
    """How ``to_si`` converts ``unit``: ``(scale, None)`` for a unit that scales, the SI
    value being ``value * scale``, or ``(1.0, reading)`` for a reading on an offset scale
    (a temperature), which Pint converts value by value.

    Kept per unit: Pint parsed each unit string again for every value, three times for
    each given, 12 of 33 s over the sweep corpora (review, 2026-11-12).
    """
    dim_spec = PARAM_SI_DIMENSIONS.get(expected_key) if expected_key else None
    # A count is a number with a name. Pint reads "turns" as the angle unit
    # (2π rad each), which made 500 solenoid turns 3142.
    if dim_spec == "dimensionless" and unit.strip().lower() in _COUNT_UNITS:
        return 1.0, None
    from app.modules.physics.givens import unit_readings
    from app.services.units import get_unit_registry

    ureg = get_unit_registry()
    readings = unit_readings(unit)
    difference = (expected_key or "").startswith("delta_")
    for index, reading in enumerate(readings):
        offset_reading = reading if reading in _OFFSET_UNITS and not difference else None
        try:
            if reading in _OFFSET_UNITS:
                quantity = ureg.Quantity(
                    1.0, _OFFSET_DIFFERENCES[reading] if difference else reading
                )
            else:
                quantity = 1.0 * ureg(reading)
        except Exception as exc:
            if index + 1 < len(readings):
                continue
            raise SolveServiceError(f"unsupported unit: {unit}") from exc
        if dim_spec is not None and quantity.dimensionality != ureg(dim_spec).dimensionality:
            # A later reading may be the one meant: Pint alone reads D as a debye.
            if index + 1 < len(readings):
                continue
            raise SolveServiceError(
                f"unit {unit} does not match expected dimension for {expected_key}"
            )
        if offset_reading is not None:
            return 1.0, offset_reading
        return float(quantity.to_base_units().magnitude), None
    raise SolveServiceError(f"unsupported unit: {unit}")


def si_factor(unit: str, *, expected_key: str | None = None) -> tuple[float, float] | None:
    """The scale from ``unit`` to SI as (numerator, denominator): km/h is 1000/3600.

    Each unit above the line scales by its own factor and each below divides by
    its own, so a student sees where the number comes from. None for a count, an
    offset unit (°C adds 273.15, it does not scale) or a unit Pint cannot split.
    """
    if not unit or unit.strip().lower() in _COUNT_UNITS:
        return None
    from app.modules.physics.givens import unit_readings
    from app.services.units import get_unit_registry

    ureg = get_unit_registry()
    try:
        whole = to_si(1.0, unit, expected_key=expected_key)
    except SolveServiceError:
        return None
    for reading in unit_readings(unit):
        if reading in _OFFSET_UNITS:
            return None
        split = _split_scale(ureg, reading)
        # The reading to_si used: its parts multiply out to the same scale.
        if split is not None and math.isclose(split[0] / split[1], whole, rel_tol=1e-9):
            return split
    return None


def _split_scale(ureg: Any, reading: str) -> tuple[float, float] | None:
    """Each unit's own scale, above the line and below it; None if Pint cannot read it."""
    numerator = denominator = 1.0
    try:
        for name, power in ureg.parse_units(reading)._units.items():
            scale, exponent = float((1 * ureg(name)).to_base_units().magnitude), float(power)
            if exponent > 0:
                numerator *= scale**exponent
            else:
                denominator *= scale ** (-exponent)
    except Exception:
        return None
    return numerator, denominator


def params_in_si(intent: PhysicsIntent) -> dict[str, float]:
    """Convert all physics_params to SI base units using Pint."""
    params = intent.physics_params or {}
    units = intent.physics_units or {}
    out: dict[str, float] = {}
    for key, val in params.items():
        unit = units.get(key, "")
        # `startswith`, not `==`: Snell's law carries `angle` and `angle2`, and
        # an angle that skipped this branch would reach `to_si` and convert
        # only because Pint's `degree` happens to base-convert to radians.
        # Anything not in radians is degrees: "30 degree" (singular) was kept as
        # 30 rad, and Snell's law then refused a negative refraction angle.
        if key.startswith("angle"):
            out[key] = val if unit.lower().startswith("rad") else math.radians(val)
        else:
            out[key] = to_si(val, unit, expected_key=key)
    return out


def solves_backwards_in_si(spec: FormulaSpec) -> bool:
    """Whether the law can be solved for an input from its stated result, which reaches it in
    SI: only when its arithmetic gives the result in an SI-sized unit. A law whose result is
    in degrees, a percent or electronvolts computes it in that unit, so a stated 42° (0.733
    rad in SI) put into its rearranged arithmetic as 0.733 degrees made a critical angle's
    refractive index 78.2, not 1.49 (review, 2026-11-11). Main declined these; so does this.
    """
    return spec.binding is not None and _si_sized(spec.binding.result[0])


@lru_cache(maxsize=256)
def _si_sized(unit: str) -> bool:
    """One of ``unit`` is one SI base unit, with no offset (radians, hertz, joules)."""
    if unit in ("", "dimensionless"):
        return True
    from app.services.units import get_unit_registry

    try:
        base: Any = (1.0 * get_unit_registry()(unit)).to_base_units()
    except (PintError, ValueError, TypeError, AttributeError):
        # An offset unit (degC) multiplies by nothing, and a unit Pint cannot read is no SI.
        return False
    return math.isclose(float(base.magnitude), 1.0, rel_tol=1e-9)


def stated_on_an_offset_scale(intent: PhysicsIntent, name: str) -> bool:
    """The stated result is a reading in °C or °F, not a difference: in SI it gains 273.15 K,
    so a change of 10 °C solved backwards was 283.15 K (review, 2026-11-11)."""
    from app.modules.physics.givens import unit_readings

    unit = (intent.physics_units or {}).get(name, "")
    readings = unit_readings(unit) if unit else ()
    return not name.startswith("delta_") and any(reading in _OFFSET_UNITS for reading in readings)
