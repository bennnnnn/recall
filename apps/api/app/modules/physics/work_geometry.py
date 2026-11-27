# ruff: noqa: RUF001 -- a question writes its minus sign as a Unicode minus too.
"""What a straight-line law of a force's work (W = Fs cos θ, P = W/t, P = Fv) cannot model.

Two shapes of question it was certified for, wrongly (textbook round, 2026-11-26):

- a turn: "turns a nut through half a turn with 270 N at a perpendicular distance of 50 cm"
  was W = 270 N x 0.5 m = 135 J, verified, for τθ = 424 J; "a torque of 100 N m over a half
  turn in 2 s" took the torque as 100 J of work, 50 W for τω = 157 W. A force that turns
  something works through an angle, which no straight-line law reads;
- an angle against another line than the motion: "pulls the rope at 50° to the horizontal
  and raises the box 1.5 m" put 50° in cos θ, 72.31 J verified, where the box rises
  vertically and the angle between the pull and the motion is 40°. θ is the angle between
  the force and the displacement; an angle measured from the horizontal is that angle only
  for a motion along the horizontal, and one from the vertical only for a vertical motion.
"""

from __future__ import annotations

import re

from app.services.law_binding.spec import FormulaSpec
from app.services.number_text import NUMBER_WORDS

_NUMBER_WORD = "|".join(
    sorted((*NUMBER_WORDS, "half", "quarter", "third", "several", "many"), key=len)[::-1]
)
# An amount of turning, after a word of turning through it: "turns it through half a turn",
# "over a half turn", "rotates 3 revolutions", "makes two full rotations", "through π rad".
# A turn named as a thing ("rounds a turn", "a 50-turn coil") is no amount turned, and a rate
# ("3 revolutions per second", "rad/s", "20 rad s^-1") none either (review of #2604).
_TURNING = (
    r"(?:through|over|by|of|turns?|turned|turning|rotates?|rotated|rotating|spins?|spun"
    r"|revolves?|makes?|made|completes?|completed)"
)
_AMOUNT = (
    rf"(?:an?\s+)?(?:(?<![\d.])\d+(?:\.\d+)?|{_NUMBER_WORD})(?:[\s-]+an?)?[\s-]+"
    r"(?:(?:full|complete|whole)\s+)?(?:turns?|revolutions?|rotations?|revs?)\b"
    r"|an?\s+(?:full|complete|whole)\s+(?:turn|revolution|rotation)\b"
    r"|(?:(?<![\d.])\d+(?:\.\d+)?|π|\\pi|\bpi)\s*(?:rad|radians?)\b"
)
_TURNED = re.compile(
    rf"\b{_TURNING}\s+(?:(?:it|the\s+\w+|its\s+\w+)\s+)?(?:through\s+)?(?:{_AMOUNT})"
    r"(?!\s*(?:/|per\b|each\b|every\b|an?\s+(?:second|minute|hour)\b|[a-z]+\s*\^\s*\{?\s*[-−]))",
    re.IGNORECASE,
)
# The kinds of input a force's work is written with.
_FORCE_OR_WORK = frozenset({"newton", "joule"})
_ENERGY_OR_POWER = frozenset({"joule", "watt"})

# The line an angle is measured from, as the question states it, in any case: "50° above the
# horizontal", "50° to the Horizontal", "an angle of 50 degrees with the ground", "at an
# angle to the vertical of 25°". A ground, a floor and the level are the horizontal; a wall
# and the upright the vertical.
_LINES = {
    "horizontal": "horizontal",
    "ground": "horizontal",
    "floor": "horizontal",
    "level": "horizontal",
    "vertical": "vertical",
    "upright": "vertical",
    "wall": "vertical",
}
_LINE = "|".join(_LINES)
_FROM = r"(?:to|from|with|off|above|below|over|under|relative\s+to)"
_ANGLE_LINE = re.compile(
    rf"(?<![\d.])\d+(?:\.\d+)?\s*(?:°|º|deg(?:rees?)?\b)\s*,?\s*(?:(?:an?\s+)?angle\s+)?"
    rf"(?:measured\s+)?{_FROM}\s+(?:the\s+)?(?P<line>{_LINE})\b"
    rf"|\bangle\s+(?:of\s+)?{_FROM}\s+(?:the\s+)?(?P<late>{_LINE})\s+of\s+\d",
    re.IGNORECASE,
)
# A motion said to be up or down: the words the lifting laws' bindings read ("raise",
# "lift", "hoist", "climb"), and "vertically".
_VERTICAL_MOTION = re.compile(
    r"\b(?:rais(?:e|es|ed|ing)|lift(?:s|ed|ing)?|hoist(?:s|ed|ing)?|ascend(?:s|ed|ing)?"
    r"|climb(?:s|ed|ing)?|vertically|straight\s+up)\b",
    re.IGNORECASE,
)
# A motion said to be along the level: "horizontally", "along the floor", "a level road".
_LEVEL_MOTION = re.compile(
    r"\b(?:horizontally|(?:along|across)\s+(?:a|an|the)\s+(?:level\s+|horizontal\s+|flat\s+)?"
    r"(?:floor|ground|road|track|table|surface|corridor)|(?:a|the)\s+(?:level|flat|horizontal)"
    r"\s+(?:floor|ground|road|track|table|surface))\b",
    re.IGNORECASE,
)


def force_work_law(spec: FormulaSpec) -> bool:
    """A straight-line law of a force's work or power: its result is an energy or a power,
    worked from a force or a work (W = Fs cos θ, P = W/t, P = Fv), never from a mass lifted."""
    result = set(spec.binding.result) if spec.binding is not None else set()
    inputs = {variable.dimension for variable in spec.variables}
    return bool(result) and result <= _ENERGY_OR_POWER and bool(inputs & _FORCE_OR_WORK)


def states_a_turn(text: str) -> bool:
    """The question turns something through an amount: half a turn, 3 revolutions, π rad."""
    return _TURNED.search(text) is not None


def angle_from_another_line(text: str) -> bool:
    """The question's angle is measured from a line (``_ANGLE_LINE``) that is not the line the
    body moves along: from the horizontal while it is raised, from the vertical while it moves
    along the level. Then it is no angle between the force and the displacement. A motion
    the question gives no line for is read as the textbook does, along the angle's line."""
    for found in _ANGLE_LINE.finditer(text):
        line = _LINES[(found["line"] or found["late"]).lower()]
        rest = text[: found.start()] + " " + text[found.end() :]
        moves = _VERTICAL_MOTION if line == "horizontal" else _LEVEL_MOTION
        if moves.search(rest) is not None:
            return True
    return False
