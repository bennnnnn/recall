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
from app.services.solving import MathServiceError


@dataclass(frozen=True)
class PhysicsResult:
    """Result of a physics solve: a LaTeX answer + optional graph/scene specs."""

    answer: str  # LaTeX, e.g. r"t = \sqrt{2 \cdot 20 / 9.81} \approx 2.02 \text{ s}"
    answer_value: str  # human-readable with units, e.g. "2.02 s"
    graph_specs: list[GraphBlockSpec] = field(default_factory=list)
    # A scene of moving bodies, where the graph is a plot of one. A solve may
    # emit both: the projectile's parabola *and* the ball flying along it.
    simulation_specs: list[SimulationBlockSpec] = field(default_factory=list)


def _latex_num(value: float, *, square: bool = False) -> str:
    """Format a number for LaTeX so ``-5^2`` is not read as ``-(5^2)``."""
    text = f"{value:g}"
    if value < 0:
        text = f"({text})"
    if square:
        return f"{text}^{{2}}"
    return text


def _latex_scientific(value: float) -> str:
    """Use textbook scientific notation instead of calculator-style ``e`` text."""
    if value == 0:
        return "0"
    exponent = math.floor(math.log10(abs(value)))
    if -3 <= exponent <= 3:
        return f"{value:g}"
    coefficient = value / (10**exponent)
    return rf"{coefficient:.7g} \times 10^{{{exponent}}}"


_PARAM_SI_DIMENSIONS: dict[str, str] = {
    "h0": "meter",
    "h": "meter",
    "d": "meter",
    "v0": "meter / second",
    "v": "meter / second",
    "m": "kilogram",
    "F": "newton",
    "t": "second",
    "a": "meter / second ** 2",
    "g": "meter / second ** 2",
    "W": "joule",
    "E_out": "joule",
    "E_in": "joule",
    # Momentum / impulse / 1D collisions.
    "m1": "kilogram",
    "m2": "kilogram",
    "x1": "meter",
    "x2": "meter",
    "v1": "meter / second",
    "v2": "meter / second",
    "dt": "second",
    "r": "meter",
    "k": "newton / meter",
    "x": "meter",
    "V": "volt",
    "I": "ampere",
    "R": "ohm",
    "R1": "ohm",
    "R2": "ohm",
    "R3": "ohm",
    "R4": "ohm",
    # Round 3 circuits. Single letters are taken (V is volt, I is ampere, R is
    # ohm), so anything new here is spelled out.
    "Q": "coulomb",
    "capacitance": "farad",
    "q1": "coulomb",
    "q2": "coulomb",
    "power": "watt",
    "E_emf": "volt",
    "r_int": "ohm",
    # Round 3 SHM. "period" and "omega" spelled out: T is tesla to Pint and a
    # temperature to thermodynamics, and a bare w is not a unit at all.
    "period": "second",
    "omega": "radian / second",
    # Round 3 waves. Every key here is spelled out: Pint reads a bare "t" as a
    # tonne, "c" as the speed of light and "pa" as a *petayear*, so a param
    # without an entry in this table is not merely unvalidated - it can convert
    # into the wrong dimension entirely and answer confidently.
    "freq": "hertz",
    "freq2": "hertz",
    "wavelength": "meter",
    "v_wave": "meter / second",
    "v_src": "meter / second",
    "v_sound": "meter / second",
    "tension": "newton",
    "linear_density": "kilogram / meter",
    "sound_power": "watt",
    "harmonic": "dimensionless",
    "mode_factor": "dimensionless",
    # Round 3 optics. `u` is SUVAT's initial velocity and `f` is not a param,
    # so the conventional letters are spelled out here too.
    "focal": "meter",
    "d_obj": "meter",
    "d_img": "meter",
    "h_obj": "meter",
    "h_img": "meter",
    # Round 3 thermal. "temp" is absolute and "delta_temp" is an interval -
    # the same number in kelvin and celsius, which "temp" is not.
    "temp": "kelvin",
    "delta_temp": "kelvin",
    "c_heat": "joule / kilogram / kelvin",
    "alpha": "1 / kelvin",
    "latent_heat": "joule / kilogram",
    "heat": "joule",
    "W_out": "joule",
    "Q_in": "joule",
    "pres": "pascal",
    "pres1": "pascal",
    "volume": "meter ** 3",
    "moles": "mole",
    # Round 3 gravitation. "M" beside "m" is case-only, but it is how the
    # formula is written and the pair always appears together.
    "M": "kilogram",
    "radius_body": "meter",
    "altitude": "meter",
    # Round 3 fluids.
    "rho": "kilogram / meter ** 3",
    "depth": "meter",
    "area": "meter ** 2",
    "A1": "meter ** 2",
    "A2": "meter ** 2",
    # Round 3 rotation. "I" is already the ampere.
    "inertia": "kilogram * meter ** 2",
    "theta": "radian",
    # Round 3 magnetism. "B" is free; "T" is not, being the tesla to Pint and a
    # temperature to thermodynamics.
    "b_field": "tesla",
    "wire_L": "meter",
    "flux": "weber",
    "viscosity": "pascal * second",
    "surface_tension": "newton / meter",
    "delta_pressure": "pascal",
    "intensity": "watt / meter ** 2",
    "intensity0": "watt / meter ** 2",
    "proper_time": "second",
    "proper_length": "meter",
    "work_function": "joule",
    "uncertainty_x": "meter",
    "quantum_n": "dimensionless",
    "emissivity": "dimensionless",
    "temp_env": "kelvin",
    "thermal_conductivity": "watt / meter / kelvin",
    # Round 3 materials.
    "sigma": "pascal",
    "E_mod": "pascal",
    "L0": "meter",
    "dL": "meter",
    "half_life": "second",
    "elapsed": "second",
    "F1": "newton",
    "F2": "newton",
    "d1": "meter",
    "d2": "meter",
    "tau": "newton * meter",
    # SUVAT initial velocity. "v" and "a" and "t" and "d" are already above.
    "u": "meter / second",
    # Pendulum length.
    "L": "meter",
    # "mu" and "angle" are intentionally absent: mu is dimensionless and angle
    # is converted by _params_in_si before any unit check runs.
}

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
    "rads/s": "radian / second",
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


# Units whose zero is not zero. These must be constructed as a Quantity rather
# than multiplied, and a *difference* in them is not the same as a value.
_OFFSET_UNITS = frozenset({"degC", "degF", "celsius", "fahrenheit"})

# CODATA, read from the unit registry rather than typed: a transposed digit in
# a hand-written constant is a wrong answer nothing else would catch.
_GAS_CONSTANT = 8.314462618153241
_BIG_G = 6.67430e-11
_PLANCK_H = 6.62607015e-34
_SPEED_OF_LIGHT = 299792458.0
_ELEMENTARY_CHARGE = 1.602176634e-19
_COULOMB_K = 8.9875517923e9
_EPSILON_0 = 8.8541878128e-12
_MU_0 = 1.25663706212e-6
_HBAR = 1.054571817e-34
_ELECTRON_MASS = 9.1093837015e-31
_STEFAN_BOLTZMANN = 5.670374419e-8
_WIEN_B = 2.897771955e-3


def _to_si(value: float, unit: str, *, expected_key: str | None = None) -> float:
    """Convert a value with a unit string to its SI base using Pint.

    Returns the value unchanged if the unit is empty (assumed already SI).
    Raises when ``expected_key`` has a known dimension and the unit does not match.
    """
    if not unit:
        return value
    from app.modules.math import get_unit_registry

    ureg = get_unit_registry()
    alias = _UNIT_ALIASES.get(unit.lower(), unit)
    try:
        if alias in _OFFSET_UNITS:
            # Celsius is an offset unit, not a scale factor: `value * ureg(
            # "degC")` raises OffsetUnitCalculusError rather than converting.
            quantity = ureg.Quantity(value, alias)
        else:
            quantity = value * ureg(alias)
        dim_spec = _PARAM_SI_DIMENSIONS.get(expected_key) if expected_key else None
        if dim_spec is not None and quantity.dimensionality != ureg(dim_spec).dimensionality:
            raise MathServiceError(
                f"unit {unit} does not match expected dimension for {expected_key}"
            )
        base = quantity.to_base_units()
        return float(base.magnitude)
    except MathServiceError:
        raise
    except Exception as exc:
        raise MathServiceError(f"unsupported unit: {unit}") from exc


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
