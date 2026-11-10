"""Substitution carried to its value: the arithmetic a student still has to do, done.

A solver stores the substituted law (``a = \\frac{27.7778 - 0}{8}``) and stops. The
reply works it one layer at a time (``reduce_substitution``) and ends on the value it
reaches, unrounded, when that value only rounds to the verified answer:

    a = \\frac{27.7778 - 0}{8}
    a = \\frac{27.7778}{8}
    a = 3.47223\\,\\mathrm{m/s²}

and the card states the answer once, rounded (3.47 m/s²). A value already the answer's own
(15 cm), or one the working's typed constants put off by more than rounding (7672.4 for a
verified 7673), closes on the verified answer instead, and the saved reply drops that line
as the card's restatement (``chat/worked_lead.drop_restated_step``).

A row is matched to the answer by value, not by name: "a and T", "50 N at 53.1°" and
"H_max and R" each have a row per value, and ``|v|`` or ``f_s`` may name it. The middle
rows are shown only when they reach a verified value (or the SI value a conversion row
then turns into the shown unit). One row and one answer close on the answer even when
the row is past reading. A row the solver already worked (``E = 2000 \\cdot 10800`` then
``E = 2.16 \\times 10^{7} J``) is left as it is.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from pint.errors import PintError

from app.modules.physics.bodies import SCHOOL_GRAVITY, SEA_LEVEL_PRESSURE
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
from app.modules.physics.display import (
    ANSWER_FIGURES,
    is_conversion_row,
    is_value_row,
    latex_given,
    latex_unit,
    quantity_number,
    si_symbol,
)
from app.modules.physics.givens import unit_readings
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.si import PARAM_SI_DIMENSIONS, to_si
from app.services.law_binding.leaf_units import LeafUnits
from app.services.law_binding.reduction import Reduction, reduce_substitution
from app.services.school_rounding import round_figures
from app.services.solving import SolveServiceError
from app.services.units import get_unit_registry

# How a verified answer joins its values (solvers/chip.py render_chip_latex).
_JOINS = re.compile(r";\\quad |\\ \\text\{(?:and|or)\}\\ |,\\ ")
# "50 N\ \text{at 53.1°}": the angle is a value of its own.
_AT = re.compile(r"\\ \\text\{at (?P<at>[^}]*)\}")
# "459 Hz\ (\text{receding, …})": a note on the value, not a value.
_NOTE = re.compile(r"\\ \((?:\\text\{[^}]*\}|[^()]*)\)\s*$")
_LEADING_SYMBOL = re.compile(r"^[^=]+=\s*")
_NUMBER = re.compile(r"(?P<number>-?\d+(?:\.\d+)?)(?:\s*\\times\s*10\^\{(?P<power>-?\d+)\})?")
_ROW = re.compile(r"^(?P<lhs>[^=]+?)\s*=\s*(?P<rhs>[^=]+)$")


def answer_parts(latex_answer: str | None) -> list[tuple[str, float]]:
    """Each value of a verified answer as (LaTeX to close a row on, its number)."""
    parts: list[tuple[str, float]] = []
    for piece in _JOINS.split((latex_answer or "").strip()):
        at = _AT.search(piece)
        pieces = [_AT.sub("", piece), at.group("at")] if at else [piece]
        for value in pieces:
            shown = _NOTE.sub("", _LEADING_SYMBOL.sub("", value.strip())).strip()
            number = _NUMBER.match(shown)
            if number is None:
                continue
            amount = float(number.group("number"))
            if number.group("power"):
                amount *= 10.0 ** int(number.group("power"))
            parts.append((shown, amount))
    return parts


def _same(worked: float, verified: float) -> bool:
    """Equal to three figures, or within 0.1%: the working's constants are rounded as
    typed, so 7672.4 worked from them is the verified 7673, and 5542 is 5545."""
    return round_figures(worked, ANSWER_FIGURES) == round_figures(
        verified, ANSWER_FIGURES
    ) or math.isclose(worked, verified, rel_tol=1e-3)


# The SI unit a working value is in, found by the answer's unit's dimension.
_SI_UNITS = ("J", "N", "W", "Pa", "m", "s", "kg", "m/s", "m/s^2", "A", "V", "C", "F", "Hz", "K")
_UNIT = re.compile(r"\\mathrm\{(?P<unit>[^}]+)\}")
# "\frac{1}{R_p} = …": a law that gives the reciprocal of what is asked.
_RECIPROCAL = re.compile(r"\\frac\{1\}\{(?P<of>[^{}]+)\}")


def _in_si(part: str) -> tuple[str, float] | None:
    """(SI unit, how many of it one of the answer's unit is): an eV is 1.602e-19 J."""
    written = _UNIT.search(part)
    if written is None:
        return None
    ureg = get_unit_registry()
    for reading in unit_readings(written.group("unit").replace("²", "^2").replace("³", "^3")):
        found = _named_si(ureg, reading)
        if found is not None:
            return found
    return None


def _named_si(ureg: Any, reading: str) -> tuple[str, float] | None:
    try:
        unit = ureg(reading)
        si = next((si for si in _SI_UNITS if ureg(si).dimensionality == unit.dimensionality), None)
        return None if si is None else (si, float((1 * unit).to(si).magnitude))
    except Exception:
        return None


def _unrounded(worked: float, shown: str) -> str:
    """``shown`` (``4.9\\,\\mathrm{m/s²}``) with the worked value in place of its number when
    the two differ only by the answer's rounding (4.905): the working ends on the value it
    reached, and only the card rounds it. Otherwise ``shown``."""
    number = _NUMBER.match(shown)
    if number is None:
        return shown
    digits = len(number.group("number").lstrip("-").replace(".", "").lstrip("0")) or 1
    stated = float(number.group("number")) * 10.0 ** int(number.group("power") or 0)
    written = latex_given(worked)
    if written == number.group(0) or round_figures(worked, digits) != round_figures(stated, digits):
        return shown
    return f"{written}{shown[number.end() :]}"


def _unit_tex(units: LeafUnits | None, reduction: Reduction | None) -> str:
    """The unit a reduction's value is shown with, "" when its numbers carry none."""
    if units is None or reduction is None or reduction.unit is None:
        return ""
    return units.shown(reduction.unit)


def _closing(
    lhs: str, reduction: Reduction | None, part: tuple[str, float], unit: str = ""
) -> list[str] | None:
    """The rows after the substitution that end on ``part``, or None when they do not reach it.

    The working's value is the answer; or its negative, when the answer is a size with a
    direction ("5000 N, opposing the motion"); or the answer in SI, when the answer is shown
    in another unit (photon energy in eV); or its reciprocal, for a law in 1/R or 1/f.
    """
    shown, verified = part
    if reduction is None:
        return None
    middle = list(reduction.rows)
    # A row for 1/R_p ends on R_p, even when the two are equal (two 2 Ω in parallel).
    reciprocal = _RECIPROCAL.fullmatch(lhs)
    if reciprocal is None and _same(reduction.value, verified):
        return [*middle, f"{lhs} = {_unrounded(reduction.value, shown)}"]
    if reciprocal is None and reduction.value < 0 < verified and _same(-reduction.value, verified):
        return [*middle, f"{lhs} = -{_unrounded(-reduction.value, shown)}"]
    if reciprocal is not None and reduction.value and _same(1 / reduction.value, verified):
        value, of = f"{latex_given(reduction.value)}{unit}", reciprocal.group("of")
        return [*middle, f"{lhs} = {value}", rf"{of} = \frac{{1}}{{{value}}}", f"{of} = {shown}"]
    si = _in_si(shown)
    if si is not None and si[1] != 1 and _same(reduction.value / si[1], verified):
        worked = f"{latex_given(reduction.value)}{latex_unit(si[0])}"
        return [*middle, f"{lhs} = {worked} = {shown}"]
    return None


def _worked_rows(rows: Sequence[str]) -> list[int]:
    """Rows that substitute into a law and stop: a left side, arithmetic, no value after."""
    found: list[int] = []
    for at, row in enumerate(rows):
        following = rows[at + 1] if at + 1 < len(rows) else None
        if is_conversion_row(row) or is_value_row(row) or _ROW.match(row) is None:
            continue
        if following is not None and is_value_row(following):
            continue
        found.append(at)
    return found


def carried_to_answer(
    rows: Sequence[str],
    latex_answer: str | None,
    given: Sequence[tuple[float, str]] = (),
) -> list[str]:
    """The solver's rows, each substitution that gives a verified value worked down to it.

    ``given`` is each given's value as the working uses it and its unit (``given_units``):
    a number of the working that is a given's carries that unit, and a worked number the
    unit it reduces to.
    """
    parts = answer_parts(latex_answer)
    units = _leaf_units(given, parts)
    worked = _worked_rows(rows)
    unused = list(parts)
    after: dict[int, list[str]] = {}
    shown_rows, reductions = _labelled(rows, worked, units)
    for at in worked:
        match = _ROW.match(rows[at])
        if match is None:
            continue
        lhs = match.group("lhs").strip()
        following = rows[at + 1] if at + 1 < len(rows) else None
        conversion = following if following is not None and is_conversion_row(following) else None
        reduction = reductions.get(at)
        if conversion is not None:
            target = quantity_number(conversion)
            if reduction is not None and target is not None and _same(reduction.value, target):
                after[at] = list(reduction.rows)
            continue
        for part in unused:
            closing = _closing(lhs, reduction, part, _unit_tex(units, reduction))
            if closing is not None:
                unused.remove(part)
                after[at] = closing
                break
        else:
            if reduction is None and len(worked) == 1 and len(parts) == 1:
                # Past reading, but the one law gives the one answer (R_p, not 1/R_p).
                reciprocal = _RECIPROCAL.fullmatch(lhs)
                named = lhs if reciprocal is None else reciprocal.group("of")
                after[at] = [f"{named} = {parts[0][0]}"]
    out: list[str] = []
    for at, row in enumerate(shown_rows):
        out.append(row)
        out.extend(after.get(at, []))
    return out


def _labelled(
    rows: Sequence[str], worked: list[int], units: LeafUnits | None
) -> tuple[list[str], dict[int, Reduction | None]]:
    """The rows with a unit by every number, in order, and each worked row's reduction.

    A value a row works out is known to the rows after it with the unit it reached:
    ``d = 24 + 75`` adds the thinking and braking distances found above it.
    """
    shown = list(rows)
    reductions: dict[int, Reduction | None] = {}
    for at, row in enumerate(rows):
        if at in worked:
            match = _ROW.match(row)
            if match is None:
                continue
            lhs, rhs = match.group("lhs").strip(), match.group("rhs").strip()
            reduction = reduce_substitution(lhs, rhs, latex_given, units)
            reductions[at] = reduction
            if reduction is not None and reduction.substituted is not None:
                shown[at] = f"{lhs} = {reduction.substituted}"
        elif units is not None:
            following = rows[at + 1] if at + 1 < len(rows) else None
            shown[at], reduction = _stated_row(row, units, following)
            stated = _stated_value(row)
            if stated is not None:
                units = replace(units, given=[*units.given, stated])
        else:
            continue
        if units is not None and reduction is not None and reduction.unit is not None:
            units = replace(units, given=[*units.given, (reduction.value, reduction.unit)])
    return shown, reductions


def _stated_value(row: str) -> tuple[float, Any] | None:
    """A row that states a value with its unit (``R_s = 5000\\,\\Omega``), as a known for
    the rows after it."""
    if not is_value_row(row):
        return None
    value = quantity_number(row)
    unit = _answer_unit(row.split(" = ", 1)[1].strip())
    return None if value is None or unit is None else (value, unit)


def _stated_row(row: str, units: LeafUnits, following: str | None) -> tuple[str, Reduction | None]:
    """``d_r = 30 \\times 0.8 = 24``, a row that states its value, with its units:
    ``d_r = 30\\,\\mathrm{m/s} \\times 0.8\\,\\mathrm{s} = 24\\,\\mathrm{m}``; or
    ``R_s = 2000 + 3000`` whose value the next row states. The value checks the reading,
    so it may end in any dimension (a time on the way to a range)."""
    sides = row.split(" = ")
    if len(sides) == 2 and following is not None and is_value_row(following):
        lhs, arithmetic = (side.strip() for side in sides)
        next_value = quantity_number(following)
        reduction = reduce_substitution(lhs, arithmetic, latex_given, replace(units, answers=None))
        if reduction is None or reduction.substituted is None or next_value is None:
            return row, None
        if not _same(reduction.value, next_value):
            return row, None
        return f"{lhs} = {reduction.substituted}", reduction
    stated = _NUMBER.fullmatch(sides[-1].strip()) if len(sides) == 3 else None
    if stated is None:
        return row, None
    lhs, arithmetic, value = (side.strip() for side in sides)
    reduction = reduce_substitution(lhs, arithmetic, latex_given, replace(units, answers=None))
    if reduction is None or reduction.substituted is None:
        return row, None
    amount = float(stated.group("number")) * 10.0 ** int(stated.group("power") or 0)
    if not _same(reduction.value, amount):
        return row, None
    unit = "" if reduction.unit is None else units.shown(reduction.unit)
    return f"{lhs} = {reduction.substituted} = {value}{unit}", reduction


def intent_givens(intent: PhysicsIntent) -> list[tuple[float, str]]:
    """``given_units`` of a physics question's stated values."""
    return given_units(intent.physics_params or {}, intent.physics_units or {})


def given_units(params: dict[str, float], units: dict[str, str]) -> list[tuple[float, str]]:
    """Each dimensional given as a working may use it, with its unit: its SI value in the SI
    unit, and its value as typed in the unit typed (a solver that works in km and h). A pure
    number (a count, η, μ) and an angle carry none."""
    found: list[tuple[float, str]] = []
    for name, value in params.items():
        dimension = PARAM_SI_DIMENSIONS.get(name)
        if dimension in (None, "dimensionless", "revolution / minute") or name.startswith("angle"):
            continue
        typed = units.get(name, "")
        try:
            si_value = to_si(value, typed, expected_key=name)
        except SolveServiceError:
            continue
        found.append((si_value, si_symbol(dimension)))
        if typed and not math.isclose(si_value, value):
            found.append((value, typed))
    return found


# The constants a working writes as numbers, with their units: G in Newton's law of
# gravitation, k_e in Coulomb's, R in the gas law. Standard gravity is one when the
# question leaves g unstated.
_CONSTANTS: tuple[tuple[float, str], ...] = (
    (SCHOOL_GRAVITY["earth"], "m/s^2"),
    (BIG_G, "N·m²/kg²"),
    (COULOMB_K, "N·m²/C²"),
    (SPEED_OF_LIGHT, "m/s"),
    (GAS_CONSTANT, "J/(mol·K)"),
    (PLANCK_H, "J·s"),
    (HBAR, "J·s"),
    (ELEMENTARY_CHARGE, "C"),
    (ELECTRON_MASS, "kg"),
    (BOLTZMANN, "J/K"),
    (EPSILON_0, "F/m"),
    (MU_0, "H/m"),
    (SEA_LEVEL_PRESSURE, "Pa"),
)
# A worked unit by its SI name when it has one: kg·m²/s² is J, kg·m/s² is N. A momentum
# stays kg·m/s.
_NAMED = ("N", "J", "W", "Pa", "C", "V", "ohm", "F", "T", "H", "Wb")


def _pint_unit(unit: str) -> Any | None:
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


# A unit as an answer writes it after its number: \\,\\mathrm{m/s²}, \\,\\Omega, \\,\\%.
_ANSWER_UNIT = re.compile(r"^\\,(?:\\mathrm\{(?P<unit>[^}]+)\}|\\(?P<command>Omega))")


def _answer_unit(shown: str) -> Any | None:
    number = _NUMBER.match(shown)
    written = _ANSWER_UNIT.match(shown[number.end() :]) if number else None
    if written is None:
        return None
    return _pint_unit(written.group("unit") or "ohm")


def _named(unit: Any) -> str | None:
    ureg = get_unit_registry()
    for name in _NAMED:
        try:
            if math.isclose(float(ureg.Quantity(1, unit).to(name).magnitude), 1.0):
                return "Ω" if name == "ohm" else name
        except (PintError, ValueError, AttributeError):
            continue
    return None


def _leaf_units(
    given: Sequence[tuple[float, str]], parts: list[tuple[str, float]]
) -> LeafUnits | None:
    if not given:
        # Without the givens a constant alone would be labelled, beside bare givens.
        return None
    readings = [(value, _pint_unit(unit), unit) for value, unit in (*given, *_CONSTANTS)]
    known = [(value, unit, text) for value, unit, text in readings if unit is not None]
    if not known or not parts:
        return None
    answers = []
    for written, _value in parts:
        unit = _answer_unit(written)
        answers.append(None if unit is None or unit.dimensionless else unit.dimensionality)
        if unit is not None and not unit.dimensionless:
            # A law in 1/R or 1/f works out the reciprocal first.
            answers.append((unit**-1).dimensionality)

    def shown(unit: Any) -> str:
        # A given's own spelling first (J/(kg·K)), then the SI name (J), else Pint's short
        # one (m/s²).
        text = next((text for _value, own, text in known if own == unit), None) or _named(unit)
        if text is None:
            text = format(unit, "~").replace(" ** ", "^").replace(" / ", "/").replace(" * ", "·")
            # 1/Ω is Ω⁻¹, as a book writes a reciprocal unit.
            if text.startswith("1/") and "/" not in text[2:] and "·" not in text:
                text = f"{text[2:]}^-1"
        return latex_unit(text)

    return LeafUnits(
        given=[(value, unit) for value, unit, _text in known], shown=shown, answers=answers
    )
