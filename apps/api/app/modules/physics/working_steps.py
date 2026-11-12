"""Substitution carried to its value: the arithmetic a student still has to do, done.

A solver stores the substituted law (``a = \\frac{27.7778 - 0}{8}``) and stops. The
reply works it one layer at a time (``reduce_substitution``) and ends on the value it
reaches, unrounded, when that value only rounds to the verified answer:

    a = \\frac{27.7778 - 0}{8}
    a = \\frac{27.7778}{8}
    a = 3.47223\\,\\mathrm{m/s²}

and the card states the answer once, rounded (3.47 m/s²). A value already the answer's own
(15 cm), or one the working's typed constants put off by more than rounding (7672.4 for a
verified 7673), closes on the verified answer instead: the working ends on its value above
the card, as a textbook's does.

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
from typing import Any

from app.modules.physics.catalog import formula_spec, select_formula
from app.modules.physics.display import (
    ANSWER_FIGURES,
    is_conversion_row,
    is_value_row,
    latex_given,
    latex_unit,
    quantity_number,
)
from app.modules.physics.givens import unit_readings
from app.modules.physics.notation import shown
from app.modules.physics.row_units import RowUnits, pint_unit, row_units
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.results import PhysicsResult
from app.services.law_binding.inverse import form_params
from app.services.law_binding.reduction import Reduction, reduce_substitution
from app.services.law_binding.symbols import plain_symbol
from app.services.school_rounding import round_figures
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


def _unit_tex(units: RowUnits | None, reduction: Reduction | None) -> str:
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
    rows: Sequence[str], latex_answer: str | None, units: RowUnits | None = None
) -> list[str]:
    """The solver's rows, each substitution that gives a verified value worked down to it.

    With ``units`` (``working_units``) each number carries the unit of the law symbol it
    stands for, and each worked number the unit it reduces to.
    """
    parts = answer_parts(latex_answer)
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
    rows: Sequence[str], worked: list[int], units: RowUnits | None
) -> tuple[list[str], dict[int, Reduction | None]]:
    """The rows with a unit by every number, in order, and each worked row's reduction.

    A value a row works out is known to the rows after it with the unit it reached:
    ``d = d_r + d_b`` adds the thinking and braking distances found above it.
    """
    shown = list(rows)
    reductions: dict[int, Reduction | None] = {}
    for at, row in enumerate(rows):
        match = _ROW.match(row)
        if at in worked:
            if match is None:
                continue
            lhs, rhs = match.group("lhs").strip(), match.group("rhs").strip()
            leaves = units.leaf_units(lhs) if units is not None else None
            reduction = reduce_substitution(lhs, rhs, latex_given, leaves)
            reductions[at] = reduction
            if units is not None and reduction is not None and reduction.substituted:
                shown[at] = f"{lhs} = {reduction.substituted}"
                units.learn(lhs, reduction.value, reduction.unit)
        elif units is not None:
            following = rows[at + 1] if at + 1 < len(rows) else None
            shown[at] = _stated_row(row, units, following, shown[at - 1] if at else None)
    return shown, reductions


def _stated_row(row: str, units: RowUnits, following: str | None, above: str | None) -> str:
    """A row that states its value, with its units: ``d_r = 30 \\times 0.8 = 24`` becomes
    ``d_r = 30\\,\\mathrm{m/s} \\times 0.8\\,\\mathrm{s} = 24\\,\\mathrm{m}``, and
    ``R_s = 2000 + 3000`` whose value the next row states. A row that only states a value
    is known to the rows after it, and takes the unit of the row above it that worked it
    out (``\\frac{1}{R_p} = 0.5`` under a row in Ω⁻¹)."""
    sides = [side.strip() for side in row.split(" = ")]
    if is_value_row(row):
        return _value_row(row, sides, units, above)
    arithmetic_value: float | None = None
    if len(sides) == 3:
        stated = _NUMBER.fullmatch(sides[2])
        if stated is not None:
            arithmetic_value = float(stated.group("number")) * 10.0 ** int(
                stated.group("power") or 0
            )
    elif len(sides) == 2 and following is not None and is_value_row(following):
        arithmetic_value = quantity_number(following)
    leaves = units.leaf_units(sides[0]) if arithmetic_value is not None else None
    if leaves is None or arithmetic_value is None:
        return row
    reduction = reduce_substitution(sides[0], sides[1], latex_given, leaves)
    if (
        reduction is None
        or not reduction.substituted
        or not _same(reduction.value, arithmetic_value)
    ):
        return row
    units.learn(sides[0], reduction.value, reduction.unit)
    if len(sides) == 2:
        return f"{sides[0]} = {reduction.substituted}"
    unit = "" if reduction.unit is None else units.stated(sides[0], reduction.unit)
    return f"{sides[0]} = {reduction.substituted} = {sides[2]}{unit}"


def _value_row(row: str, sides: list[str], units: RowUnits, above: str | None) -> str:
    value = quantity_number(row)
    if value is None:
        return row
    unit = _answer_unit(sides[-1])
    if unit is not None:
        units.learn(sides[0], value, unit)
        return row
    if above is None or not above.startswith(f"{sides[0]} = ") or len(sides) != 2:
        return row
    worked = units.known.get(_plain(sides[0]), [])
    if not worked or not _same(worked[-1][0], value) or worked[-1][1] is None:
        return row
    reached = worked[-1][1]
    if reached.dimensionless:
        return row
    return f"{row}{units.shown(reached)}"


def working_units(
    intent: PhysicsIntent,
    formulas: Sequence[str],
    latex_answer: str | None,
    operation: str | None = None,
) -> RowUnits:
    """What ``intent``'s working numbers stand for: its law rows, its givens, the answer."""
    operation = operation or intent.physics_op or ""
    rows = list(formulas)
    spec = formula_spec(operation)
    if spec is not None:
        base, lines, _assumptions = select_formula(
            spec, form_params(spec, intent.physics_params or {})
        )
        rows += [shown(row, operation) for row in (base, *lines) if row]
    answers: list[tuple[float, Any]] = []
    ureg = get_unit_registry()
    for written, value in answer_parts(latex_answer):
        unit = _answer_unit(written)
        if unit is None:
            answers.append((value, ureg.dimensionless))
            continue
        answers.append((float(ureg.Quantity(value, unit).to_base_units().magnitude), unit))
    return row_units(intent, rows, answers, operation)


def result_units(
    intent: PhysicsIntent, result: PhysicsResult, latex_answer: str | None
) -> RowUnits:
    """``working_units`` for a solver's result."""
    return working_units(intent, result.formulas, latex_answer)


# A unit as an answer writes it after its number: \\,\\mathrm{m/s²}, \\,\\Omega, \\,\\%.
_ANSWER_UNIT = re.compile(r"^\\,(?:\\mathrm\{(?P<unit>[^}]+)\}|\\(?P<command>Omega))")


def _answer_unit(shown: str) -> Any | None:
    number = _NUMBER.match(shown)
    written = _ANSWER_UNIT.match(shown[number.end() :]) if number else None
    if written is None:
        return None
    return pint_unit(written.group("unit") or "ohm")


def _plain(symbol: str) -> str:
    return plain_symbol(symbol)
