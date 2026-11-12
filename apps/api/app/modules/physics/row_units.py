"""What a physics working's numbers stand for, so each can carry its unit.

A substituted row puts numbers into a law: ``a = \\frac{48 - 8}{10}`` under
``a = \\frac{v_f - v_i}{t}``. The law's rows say which symbol each number replaced
(``law_binding.leaf_units``); this module says what each symbol is: a given's value in SI
and as typed, with its unit, a constant the law writes (g, G, c), or a value a row above
worked out. It also says what dimension each row's quantity may have, from the verified
answer and the catalog's symbols, so a row whose units do not end in it stays bare.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from pint.errors import PintError

from app.modules.physics.bodies import SCHOOL_GRAVITY, SEA_LEVEL_PRESSURE
from app.modules.physics.catalog import CATALOG, symbol_for
from app.modules.physics.constants import (
    BIG_G,
    BOLTZMANN,
    COULOMB_K,
    ELECTRON_MASS,
    ELEMENTARY_CHARGE,
    EPSILON_0,
    GAS_CONSTANT,
    HBAR,
    MU_0,
    PLANCK_H,
    SPEED_OF_LIGHT,
)
from app.modules.physics.display import latex_unit, si_symbol
from app.modules.physics.givens import unit_readings
from app.modules.physics.notation import shown as shown_symbol
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.si import PARAM_SI_DIMENSIONS, to_si
from app.services.law_binding.leaf_units import LeafUnits
from app.services.law_binding.symbols import plain_symbol
from app.services.solving import SolveServiceError
from app.services.units import get_unit_registry

# The constants a law writes by symbol, with their units; a number under one of these
# symbols is the constant only when its value is.
_CONSTANTS: dict[str, tuple[float, str]] = {
    "g": (SCHOOL_GRAVITY["earth"], "m/s^2"),
    "G": (BIG_G, "N·m²/kg²"),
    "k_e": (COULOMB_K, "N·m²/C²"),
    "k": (COULOMB_K, "N·m²/C²"),
    "c": (SPEED_OF_LIGHT, "m/s"),
    "h": (PLANCK_H, "J·s"),
    "\\hbar": (HBAR, "J·s"),
    "e": (ELEMENTARY_CHARGE, "C"),
    "m_e": (ELECTRON_MASS, "kg"),
    "R": (GAS_CONSTANT, "J/(mol·K)"),
    "k_B": (BOLTZMANN, "J/K"),
    "\\epsilon_0": (EPSILON_0, "F/m"),
    "\\varepsilon_0": (EPSILON_0, "F/m"),
    "\\mu_0": (MU_0, "H/m"),
    "P_0": (SEA_LEVEL_PRESSURE, "Pa"),
}
_RECIPROCAL = re.compile(r"\\frac\{1\}\{(?P<of>[^{}]+)\}")
_BARS = re.compile(r"^(?:\||\\lvert)(?P<of>.+?)(?:\||\\rvert)$")


def pint_unit(unit: str) -> Any | None:
    """A unit as written (``m/s²``, ``J/(kg·K)``, ``Ω m``) as a Pint unit, or None."""
    ureg = get_unit_registry()
    spelled = unit.replace("²", "^2").replace("³", "^3").replace("⁴", "^4").replace("·", "*")
    for reading in (*unit_readings(spelled), spelled):
        try:
            quantity = ureg(reading)
        except (PintError, ValueError, AttributeError):
            continue
        if hasattr(quantity, "units") and math.isclose(float(quantity.magnitude), 1.0):
            return quantity.units
    return None


def _dimensions(unit: str) -> Any | None:
    """A catalog dimension (``meter / second``) as a Pint dimensionality; None when pure."""
    if unit == "dimensionless":
        return None
    read = pint_unit(unit)
    return None if read is None or read.dimensionless else read.dimensionality


def _base(symbol: str) -> str:
    """The letter a symbol is written with: ``d_r`` is d, ``E_{k,f}`` is E."""
    text = symbol.removeprefix("\\Delta")
    for mark in ("_", "'"):
        text = text.split(mark, 1)[0]
    return text


@lru_cache(maxsize=1)
def _catalog_dimensions() -> tuple[dict[str, set[Any]], dict[str, set[Any]]]:
    """Every dimension each symbol, and each symbol's letter, has anywhere in the catalog."""
    by_symbol: dict[str, set[Any]] = {}
    for spec in CATALOG.values():
        named = {variable.name: variable for variable in spec.variables}
        pairs = [
            (variable.symbol, variable.dimension or "dimensionless")
            for variable in spec.variables
            if variable.visible
        ]
        pairs += [
            (symbol, named[name].dimension or "dimensionless")
            for name, symbol in spec.solve_for
            if name in named
        ]
        if spec.binding is not None and spec.binding.result:
            pairs.append((spec.result_symbol, spec.binding.result[0]))
        for symbol, unit in pairs:
            dimension = _dimensions(unit)
            for spelling in {symbol, shown_symbol(symbol, spec.id)}:
                by_symbol.setdefault(plain_symbol(spelling), set()).add(dimension)
    by_letter: dict[str, set[Any]] = {}
    for symbol, dimensions in by_symbol.items():
        by_letter.setdefault(_base(symbol), set()).update(dimensions)
    return by_symbol, by_letter


@dataclass
class RowUnits:
    """What a working's symbols stand for; rows add the values they work out."""

    formulas: tuple[str, ...]
    known: dict[str, list[tuple[float, Any]]] = field(default_factory=dict)
    spellings: list[tuple[Any, str]] = field(default_factory=list)
    # The SI spelling of a quantity this law names (J for its work, N·m for its torque).
    kinds: dict[str, str] = field(default_factory=dict)
    # Each verified answer value in SI, with its Pint unit.
    answers: list[tuple[float, Any]] = field(default_factory=list)

    def leaf_units(self, lhs: str) -> LeafUnits | None:
        """What a row that works out ``lhs`` may put its numbers into, or None."""
        wanted = plain_symbol(lhs)
        rows = [row for row in self.formulas if plain_symbol(row.split("=", 1)[0]) == wanted]
        if not rows:
            # A law named by its letter (H) for a row named in full (H_{max}): the one law
            # written with that letter, when there is exactly one.
            rows = [
                row
                for row in self.formulas
                if _base(plain_symbol(row.split("=", 1)[0])) == _base(wanted)
            ]
            rows = rows if len({plain_symbol(row.split("=", 1)[0]) for row in rows}) == 1 else []
        sides = [side.strip() for row in rows for side in row.split("=")[1:]]
        if not sides:
            return None
        return LeafUnits(
            formulas=sides,
            known=self.known,
            shown=self.shown,
            dimensions=lambda value: self.dimensions(lhs, value),
        )

    def learn(self, lhs: str, value: float, unit: Any) -> None:
        self.known.setdefault(plain_symbol(lhs), []).append((value, unit))

    def shown(self, unit: Any) -> str:
        """A unit after a number: a given's own spelling (J/(kg·K)), else as it composes
        (kg·m²/s² stays that, never renamed by its dimension alone)."""
        text = next((text for own, text in self.spellings if own == unit), None)
        if text is None:
            text = _composed(_simplest(unit))
            # 1/Ω is Ω⁻¹ and 1/s² is s⁻², as a book writes a reciprocal unit.
            reciprocal = re.fullmatch(r"1/([^/·^]+)(?:\^(\d+))?", text)
            if reciprocal is not None:
                text = f"{reciprocal.group(1)}^-{reciprocal.group(2) or 1}"
        return latex_unit(text)

    def stated(self, lhs: str, unit: Any) -> str:
        """The unit a row's own quantity is stated in: this law's name for it when the units
        agree (work in J, torque in N·m), else as they compose."""
        kind = self.kinds.get(plain_symbol(lhs))
        named = None if kind is None else pint_unit(kind)
        if named is not None and _same_unit(named, unit):
            return latex_unit(kind or "")
        return self.shown(unit)

    def dimensions(self, lhs: str, value: float) -> set[Any]:
        """The dimensions the quantity ``lhs`` may have: an answer it equals, its symbol's in
        the catalog, or failing that its letter's."""
        found: set[Any] = set()
        for answer, unit in self.answers:
            dimension = None if unit.dimensionless else unit.dimensionality
            if _same(value, answer):
                found.add(dimension)
            elif answer and _same(value, 1 / answer) and dimension is not None:
                found.add((unit**-1).dimensionality)
        symbol = plain_symbol(lhs)
        bars = _BARS.match(symbol)
        symbol = bars.group("of") if bars else symbol
        reciprocal = _RECIPROCAL.fullmatch(symbol)
        by_symbol, by_letter = _catalog_dimensions()
        of = reciprocal.group("of") if reciprocal else symbol
        dimensions = by_symbol.get(of) or by_letter.get(_base(of), set())
        if reciprocal:
            dimensions = {None if each is None else each**-1 for each in dimensions}
        return found | dimensions


def _composed(unit: Any) -> str:
    """Pint's short spelling, a named unit first as a book writes it: N·m, not m·N."""
    text = format(unit, "~").replace(" ** ", "^").replace(" / ", "/").replace(" * ", "·")
    top, slash, bottom = text.partition("/")
    factors = sorted(top.split("·"), key=lambda factor: not factor[:1].isupper())
    return "·".join(factors) + slash + bottom


def _simplest(unit: Any) -> Any:
    """The unit as it composes (N·m stays N·m), or in SI base units when that is simpler:
    kg·m/N is s², and its root s, never kg⁰·⁵·m⁰·⁵/N⁰·⁵."""
    base = (1 * unit).to_base_units()
    if not math.isclose(float(base.magnitude), 1.0):
        return unit
    composed, reduced = _composed(unit), _composed(base.units)
    fractional = "." in composed
    if fractional or len(re.split("[·/]", reduced)) < len(re.split("[·/]", composed)):
        return base.units
    return unit


def _same(value: float, other: float) -> bool:
    return math.isclose(value, other, rel_tol=1e-3)


def _same_unit(left: Any, right: Any) -> bool:
    if left.dimensionality != right.dimensionality:
        return False
    try:
        return math.isclose(float((1 * left).to(right).magnitude), 1.0)
    except (PintError, ValueError):
        return False


def row_units(
    intent: PhysicsIntent,
    formulas: Sequence[str],
    answers: Sequence[tuple[float, Any]],
    operation: str | None = None,
) -> RowUnits:
    """The working's symbols for ``operation`` (the intent's, or one part's)."""
    operation = operation or intent.physics_op or ""
    spec = CATALOG.get(operation)
    units = RowUnits(formulas=tuple(formulas), answers=list(answers))
    typed = intent.physics_units or {}
    for name, value in (intent.physics_params or {}).items():
        written = symbol_for(spec, name) if spec is not None else None
        dimension = PARAM_SI_DIMENSIONS.get(name)
        if not written or dimension is None or name.startswith("angle"):
            continue
        symbol = shown_symbol(written, operation)
        if dimension in ("dimensionless", "revolution / minute"):
            units.learn(symbol, value, get_unit_registry().dimensionless)
            continue
        _learn_given(units, symbol, value, typed.get(name, ""), name, dimension)
    for symbol, (value, unit) in _CONSTANTS.items():
        constant = pint_unit(unit)
        if constant is not None:
            units.learn(symbol, value, constant)
            units.spellings.append((constant, unit))
    if spec is not None:
        for variable in spec.variables:
            if variable.dimension:
                kind = shown_symbol(variable.symbol, operation)
                units.kinds[plain_symbol(kind)] = _spelled(si_symbol(variable.dimension))
        if spec.binding is not None and spec.binding.result:
            kind = shown_symbol(spec.result_symbol, operation)
            units.kinds[plain_symbol(kind)] = _spelled(si_symbol(spec.binding.result[0]))
    return units


def _spelled(unit: str) -> str:
    """``N*m`` as a book writes it: N·m."""
    return unit.replace("*", "·")


def _learn_given(
    units: RowUnits, symbol: str, value: float, typed: str, name: str, dimension: str
) -> None:
    """A given in SI, and as typed when the working may use it so (150 km in 2 h)."""
    si_unit = _spelled(si_symbol(dimension))
    try:
        si_value = to_si(value, typed, expected_key=name)
    except SolveServiceError:
        return
    readings = [(si_value, si_unit)]
    if typed and not math.isclose(si_value, value):
        readings.append((value, typed))
    for amount, spelled in readings:
        unit = pint_unit(spelled)
        if unit is not None:
            units.learn(symbol, amount, unit)
            units.spellings.append((unit, spelled))
