"""Shared result types, physical constants, and SI-unit conversion."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from app.models.schemas.math import GraphBlockSpec
from app.models.schemas.physics import (
    PhysicsIntent,
    SimulationBlockSpec,
)
from app.modules.physics.solvers.chip import render_chip, render_chip_latex
from app.services.solving import SolveServiceError


@dataclass(frozen=True, slots=True)
class QuantityResult:
    """One measured result. Notes such as gauge pressure live in ``detail``.

    The value is shown to three significant figures (``physics.display``);
    a solver never chooses its own number format.
    """

    symbol: str
    value: float
    unit: str = ""
    detail: str | None = None
    # "paren" -> "12 Pa (gauge)"; "suffix" -> "4 A leaving"; "at" -> "5 N at 30°".
    detail_style: str = "paren"


@dataclass(frozen=True)
class PhysicsResult:
    """Solver output. The chip is rendered from ``quantities``, never parsed back."""

    answer: str
    answer_value: str = ""
    answer_latex: str = ""
    quantities: tuple[QuantityResult, ...] = ()
    formulas: tuple[str, ...] = ()
    substitutions: tuple[str, ...] = ()
    joiner: str = " and "
    graph_specs: list[GraphBlockSpec] = field(default_factory=list)
    # A scene of moving bodies, where the graph is a plot of one. A solve may
    # emit both: the projectile's parabola *and* the ball flying along it.
    simulation_specs: list[SimulationBlockSpec] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.quantities:
            object.__setattr__(self, "answer_value", render_chip(self.quantities, self.joiner))
            object.__setattr__(
                self, "answer_latex", render_chip_latex(self.quantities, self.joiner)
            )


def solved(
    *quantities: QuantityResult,
    answer: str,
    formula: str = "",
    substitution: str = "",
    formulas: tuple[str, ...] = (),
    substitutions: tuple[str, ...] = (),
    joiner: str = " and ",
    graph_specs: list[GraphBlockSpec] | None = None,
    simulation_specs: list[SimulationBlockSpec] | None = None,
) -> PhysicsResult:
    """Build the chip and keep the formula and the substitution unparsed."""
    formula_rows = formulas or ((formula,) if formula else ())
    substitution_rows = substitutions or ((substitution,) if substitution else ())
    return PhysicsResult(
        answer=answer,
        quantities=quantities,
        formulas=formula_rows,
        substitutions=substitution_rows,
        joiner=joiner,
        graph_specs=list(graph_specs or []),
        simulation_specs=list(simulation_specs or []),
    )


def quadratic_roots(a: float, b: float, c: float) -> tuple[float, ...]:
    """Real roots of ``a·x² + b·x + c = 0``, ascending; linear when ``a`` is 0.

    The closed form, in the cancellation-free arrangement: a plain quadratic
    does not need a symbolic solver on the request path.
    """
    if a == 0:
        return () if b == 0 else (-c / b,)
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return ()
    q = -0.5 * (b + math.copysign(math.sqrt(discriminant), b))
    if q == 0:
        return (0.0,)
    return tuple(sorted({q / a, c / q}))


def _latex_num(value: float, *, square: bool = False) -> str:
    """Format a number for LaTeX so ``-5^2`` is not read as ``-(5^2)``."""
    text = f"{value:g}"
    if value < 0:
        text = f"({text})"
    if square:
        return f"{text}^{{2}}"
    return text


def _dimensions_from_catalog() -> dict[str, str]:
    """SI dimension of every declared variable. The catalog is the only list."""
    from app.modules.physics.catalog import CATALOG

    dims: dict[str, str] = {}
    for spec in CATALOG.values():
        for variable in spec.variables:
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


_PARAM_SI_DIMENSIONS: dict[str, str] = _dimensions_from_catalog()

_UNIT_ALIASES = {
    "m/s2": "m/s**2",
    "m/s^2": "m/s**2",
    "deg": "deg",
    "degrees": "deg",
    "°": "deg",
    "miles per hour": "mph",
    "miles": "mile",
    "ohms": "ohm",
    "volts": "volt",
    "amps": "ampere",
    "amperes": "ampere",
    # Pint is case-sensitive and unforgiving about the symbols people type:
    # bare "pa" is a petayear, "t" a tonne, "c" the speed of light, and "w",
    # "n", "j", "hz" are not units at all. Every extractor regex here is
    # IGNORECASE, so the lowercase spellings do arrive.
    "w": "watt",
    "watts": "watt",
    "kw": "kilowatt",
    "kilowatts": "kilowatt",
    "c/m": "coulomb / meter",
    "c/m^2": "coulomb / meter ** 2",
    "c/m2": "coulomb / meter ** 2",
    "uc/m": "microcoulomb / meter",
    "uc/m^2": "microcoulomb / meter ** 2",
    "c": "coulomb",
    "coulombs": "coulomb",
    "uc": "microcoulomb",
    "microcoulomb": "microcoulomb",
    "microcoulombs": "microcoulomb",
    "f": "farad",
    "farads": "farad",
    "uf": "microfarad",
    "µf": "microfarad",
    "nf": "nanofarad",
    "pf": "picofarad",
    "j": "joule",
    "joules": "joule",
    "ev": "electron_volt",
    "kev": "kiloelectron_volt",
    "mev": "megaelectron_volt",
    "rad/s": "radian / second",
    "rad/s^2": "radian / second ** 2",
    "rad/s2": "radian / second ** 2",
    "rads/s": "radian / second",
    "n*m": "newton * meter",
    "n·m": "newton * meter",
    "kg*m^2/s": "kilogram * meter ** 2 / second",
    "kg m^2/s": "kilogram * meter ** 2 / second",
    "radians/s": "radian / second",
    "rad/sec": "radian / second",
    "hz": "hertz",
    "khz": "kilohertz",
    "mhz": "megahertz",
    "pa": "pascal",
    "kpa": "kilopascal",
    "mpa": "megapascal",
    "k": "kelvin",
    "kelvins": "kelvin",
    "\u00b0c": "degC",
    "celsius": "degC",
    "j/kg/k": "joule / kilogram / kelvin",
    "j/(kg k)": "joule / kilogram / kelvin",
    "j/kgk": "joule / kilogram / kelvin",
    "j/kg": "joule / kilogram",
    "kj/kg": "kilojoule / kilogram",
    "kg/m": "kilogram / meter",
    "g/m": "gram / meter",
    "n/m": "newton / meter",
    "pa*s": "pascal * second",
    "pa·s": "pascal * second",
    "w/m^2": "watt / meter**2",
    "w/m2": "watt / meter**2",
    "w/m/k": "watt / meter / kelvin",
    "1/k": "1 / kelvin",
    "/k": "1 / kelvin",
    "1/°c": "1 / kelvin",
    "/°c": "1 / kelvin",
    "m^3": "m**3",
    "m3": "m**3",
    "cm^3": "cm**3",
    "cm3": "cm**3",
    "litres": "liter",
    "litre": "liter",
    "liters": "liter",
    "moles": "mole",
    "m^2": "m**2",
    "m2": "m**2",
    "cm^2": "cm**2",
    "cm2": "cm**2",
    "mm^2": "mm**2",
    "kg/m^3": "kg/m**3",
    "kg/m3": "kg/m**3",
    "g/cm^3": "g/cm**3",
    "g/cm3": "g/cm**3",
    "kg*m^2": "kg * m**2",
    "kg m^2": "kg * m**2",
    "kgm^2": "kg * m**2",
    "rad": "radian",
    "radians": "radian",
    "t": "tesla",
    "tesla": "tesla",
    "teslas": "tesla",
    "mt": "millitesla",
    "wb": "weber",
    "weber": "weber",
    "webers": "weber",
    "n": "newton",
    "newtons": "newton",
    "gpa": "gigapascal",
    "nm": "nanometer",
    "nanometer": "nanometer",
    "nanometers": "nanometer",
    "um": "micrometer",
    "µm": "micrometer",
    "micrometer": "micrometer",
    "micrometers": "micrometer",
}


# R1..R4 name a resistor network's members. Single-digit, so plain `sorted`
# orders them correctly.
_RESISTOR_KEY_RE = re.compile(r"R[1-9]")


# Words that count rather than measure: a dimensionless input written with one.
_COUNT_UNITS = frozenset({"turns", "turn", "lines", "nuclei", "atoms", "microstates"})

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


def _registry_constant(name: str) -> float:
    """One CODATA magnitude from the shared unit registry, in SI base units."""
    from app.services.units import get_unit_registry

    quantity = get_unit_registry().Quantity(1, name)
    return float(quantity.to_base_units().magnitude)


# Loaded once. A test pins each magnitude so a Pint upgrade cannot move an answer.
_GAS_CONSTANT = _registry_constant("molar_gas_constant")
_BIG_G = _registry_constant("gravitational_constant")
_PLANCK_H = _registry_constant("planck_constant")
_SPEED_OF_LIGHT = _registry_constant("speed_of_light")
_ELEMENTARY_CHARGE = _registry_constant("elementary_charge")
_EPSILON_0 = _registry_constant("vacuum_permittivity")
_MU_0 = _registry_constant("vacuum_permeability")
_HBAR = _registry_constant("hbar")
_ELECTRON_MASS = _registry_constant("electron_mass")
_STEFAN_BOLTZMANN = _registry_constant("stefan_boltzmann_constant")
_WIEN_B = _registry_constant("wien_wavelength_displacement_law_constant")
_BOLTZMANN = _registry_constant("boltzmann_constant")
_RYDBERG = _registry_constant("rydberg_constant")
_BOHR_RADIUS = _registry_constant("bohr_radius")
_COULOMB_K = 1.0 / (4.0 * math.pi * _EPSILON_0)


def _to_si(value: float, unit: str, *, expected_key: str | None = None) -> float:
    """Convert a value with a unit string to its SI base using Pint.

    Returns the value unchanged if the unit is empty (assumed already SI).
    Raises when ``expected_key`` has a known dimension and the unit does not match.
    """
    if not unit:
        return value
    dim_spec = _PARAM_SI_DIMENSIONS.get(expected_key) if expected_key else None
    # A count is a number with a name. Pint reads "turns" as the angle unit
    # (2π rad each), which made 500 solenoid turns 3142.
    if dim_spec == "dimensionless" and unit.strip().lower() in _COUNT_UNITS:
        return value
    from app.modules.physics.givens import unit_expression
    from app.services.units import get_unit_registry

    ureg = get_unit_registry()
    # "0.8c" is the speed of light; the lowercased alias table reads c as C.
    alias = "speed_of_light" if unit == "c" else _UNIT_ALIASES.get(unit.lower(), unit)
    # A spelling Pint cannot read ("lines per mm") is still one the givens
    # scanner names; its unit is the second reading.
    readings = [alias, *([table] if (table := unit_expression(unit)) not in (None, alias) else [])]
    for index, reading in enumerate(readings):
        try:
            if reading in _OFFSET_UNITS:
                # Celsius is an offset unit, not a scale factor: `value * ureg(
                # "degC")` raises OffsetUnitCalculusError rather than converting.
                difference = (expected_key or "").startswith("delta_")
                quantity = ureg.Quantity(
                    value, _OFFSET_DIFFERENCES[reading] if difference else reading
                )
            else:
                quantity = value * ureg(reading)
        except Exception as exc:
            if index + 1 < len(readings):
                continue
            raise SolveServiceError(f"unsupported unit: {unit}") from exc
        if dim_spec is not None and quantity.dimensionality != ureg(dim_spec).dimensionality:
            raise SolveServiceError(
                f"unit {unit} does not match expected dimension for {expected_key}"
            )
        return float(quantity.to_base_units().magnitude)
    raise SolveServiceError(f"unsupported unit: {unit}")


def _params_in_si(intent: PhysicsIntent) -> dict[str, float]:
    """Convert all physics_params to SI base units using Pint."""
    params = intent.physics_params or {}
    units = intent.physics_units or {}
    out: dict[str, float] = {}
    for key, val in params.items():
        unit = units.get(key, "")
        # `startswith`, not `==`: Snell's law carries `angle` and `angle2`, and
        # an angle that skipped this branch would reach `_to_si` and convert
        # only because Pint's `degree` happens to base-convert to radians.
        if key.startswith("angle"):
            lower_unit = unit.lower()
            if lower_unit in ("rad", "radian", "radians"):
                out[key] = val
            else:
                out[key] = math.radians(val) if lower_unit in ("deg", "degrees", "°", "") else val
        else:
            out[key] = _to_si(val, unit, expected_key=key)
    return out
