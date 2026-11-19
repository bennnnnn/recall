"""A verified answer reads the whole question: a part left unread declines it.

A reader takes the part of a question it recognises and fills the rest with its law's
default. In the Grade 7 and Grade 8 books (2026-11-19) that put a check mark on nine wrong
numbers: "1.36 × 104 kg/m3" was 104 kg/m³ (the mantissa and the "×" unread), "60 km/h north
to 80 m/s south" two speeds the same way (the directions unread), "its average velocity"
the final one (the "average" unread). So a verified physics answer accounts for every part
of its question that changes the answer:

- every number: one in words beside a unit (``spelled``), and one joined to another by an
  operator no reader folds ("4 × 100 m", "270 N ÷ 0.00036 m2"); a power of ten that lost its
  superscript is notation, read before this (``numbers.fold_lost_powers``);
- a stated equivalence ("1 liter of water = 1 kg of water") that the reader of equivalences
  did not apply (``stated_equivalence``): its 1 kg is never the mass;
- every direction: two values of one quantity at the two ends of a change, stated in
  opposite directions, are read with opposite signs;
- every asked quantity: the end of the change it is at, or the whole change (an average),
  is the law's result's (``asked_end_check``).

A stated value of a kind the law never uses is ``accounting``'s (a distractor, or a
competing given), and a required input a reader would fill with its own default is that
reader's to decline. Anything unread declines the verification: the turn goes to the model,
and to the formal check where it applies, never to a law's default.
"""

from __future__ import annotations

import logging
import re
from itertools import product

from app.modules.physics.catalog import formula_spec
from app.modules.physics.givens import Given, scan_givens
from app.modules.physics.numbers import quantity_unit_at
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.spelled import has_unread_quantity
from app.modules.physics.stated_equivalence import states_an_equivalence
from app.services.law_binding.roles import variable_role
from app.services.law_binding.spec import FormulaSpec
from app.services.law_binding.units import dimension_of

logger = logging.getLogger(__name__)

# Two numbers joined by an operator: "4 × 100 m", "270 N ÷ 0.00036 m2", "0.039 m − 0.0023 m".
# A unit may sit on the first ("2 m × 3 m"). The minus is the minus sign: a hyphen between
# two numbers is a range ("3-4 m"), which the givens scan reads as one unit shared.
_JOINED = re.compile(
    r"(?<![\w.])\d+(?:\.\d+)?(?:[eE][-+]?\d+)?[ \t]*(?:[A-Za-zµμΩ°/^]{1,8}\d?[ \t]*)?\)?[ \t]*"
    r"(?:[×xX*·÷]|(?<=\s)[−+](?=\s))[ \t]*\(?[ \t]*[-−]?\.?\d"
)


def unread_in_request(text: str) -> str | None:
    """What kind of part of the question no reader reads, before any reader runs; None when
    it reads them all.

    ``text`` has its units in the readers' spellings (``normalize_physics_units``), so a
    stated equivalence the reader applied is gone from it.
    """
    if has_unread_quantity(text, quantity_unit_at):
        # "dropped from ten metres onto a 1 m table": the ten metres unread, the 1 m table
        # answered another question.
        return "a quantity in words"
    if _JOINED.search(text) is not None:
        return "an operator joining two numbers"
    if states_an_equivalence(text):
        return "a stated equivalence"
    return None


def unread_in_reading(intent: PhysicsIntent, text: str) -> str | None:
    """What kind of part of the question this reading left unread; None when it read every
    part."""
    ops = [intent.physics_op, *(str(op) for op in intent.requested_ops)]
    specs = [spec for op in dict.fromkeys(ops) if op and (spec := formula_spec(op)) is not None]
    params = intent.physics_params or {}
    if any(_directions_unread(spec, params, text) for spec in specs):
        return "opposite directions read as one"
    return None


def logged(unread: str | None, op: str | None) -> bool:
    """Whether a part was left unread, logged when one was."""
    if unread is not None:
        logger.info("physics solve declined: %s unread by op=%s", unread, op)
    return unread is not None


# A direction written beside a value: "60 km/h north", "20 m/s due east", "10 N to the left",
# "moving west at 4 m/s". "up to 10 m/s" and "down to 5 m/s" name an amount, not a way.
_WAY = r"(?P<way>east|west|north|south|left|right|up(?!\s+to\b)|down(?!\s+to\b))(?:wards?)?\b"
_WAY_AFTER = re.compile(
    rf"[ \t]*(?:due[ \t]+|to(?:wards?)?[ \t]+the[ \t]+|towards?[ \t]+)?{_WAY}", re.IGNORECASE
)
_WAY_BEFORE = re.compile(
    rf"\b{_WAY}\s+(?:at|with\s+(?:a\s+)?(?:speed|velocity)\s+of)\s*$", re.IGNORECASE
)
_AXES = {
    "east": ("east-west", 1),
    "west": ("east-west", -1),
    "north": ("north-south", 1),
    "south": ("north-south", -1),
    "right": ("left-right", 1),
    "left": ("left-right", -1),
    "up": ("up-down", 1),
    "down": ("up-down", -1),
}
# How far before a value its direction may be written: "moving west at ".
_WAY_REACH = 40


def _way(given: Given, text: str) -> tuple[str, int] | None:
    """The axis and sense a direction written beside this value gives it."""
    unit = re.compile(rf"[ \t]*{re.escape(given.unit)}") if given.unit else None
    after = unit.match(text, given.end) if unit is not None else None
    found = _WAY_AFTER.match(text, after.end() if after else given.end) or _WAY_BEFORE.search(
        text[max(0, given.start - _WAY_REACH) : given.start]
    )
    return None if found is None else _AXES[found.group("way").lower()]


def _opposed_kinds(text: str) -> set[str]:
    """The kinds of which the question states two values in opposite directions."""
    directed = [
        (given.dimension, way)
        for given in scan_givens(text)
        if given.dimension is not None and (way := _way(given, text)) is not None
    ]
    return {
        kind
        for (kind, (axis, sense)), (other, (other_axis, other_sense)) in product(directed, repeat=2)
        if kind == other and axis == other_axis and sense != other_sense
    }


def _directions_unread(spec: FormulaSpec, params: dict[str, float], text: str) -> bool:
    """The law's start and end values of one kind, stated in opposite directions, read with
    one sign: "60 km/h north to 80 m/s south" became (80 - 16.7)/20 for (-80 - 16.7)/20."""
    kinds = _opposed_kinds(text)
    if not kinds:
        return False
    ends: dict[tuple[str, str], list[float]] = {}
    for variable in spec.variables:
        role = variable_role(variable)
        kind = dimension_of(variable.dimension or "")
        value = params.get(variable.name)
        if role is not None and kind in kinds and value:
            ends.setdefault((kind, role), []).append(value)
    return any(
        (start > 0) == (end > 0)
        for kind in kinds
        for start, end in product(ends.get((kind, "initial"), []), ends.get((kind, "final"), []))
    )
