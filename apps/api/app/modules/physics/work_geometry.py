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
from app.services.law_binding.words import angle_to, word_pattern
from app.services.number_text import NUMBER_WORDS

_AMOUNT = "|".join(
    sorted((*NUMBER_WORDS, "an?", "half", "quarter", "third", "several", "many"), key=len)[::-1]
)
# An amount of turning: "half a turn", "through 3 revolutions", "two full rotations",
# "through π rad". A rate ("3 revolutions per second", "rad/s") is no amount turned.
_TURNED = re.compile(
    rf"(?:\b(?:(?<![\d.])\d+(?:\.\d+)?|{_AMOUNT})(?:[\s-]+an?)?[\s-]+(?:(?:full|complete|whole)\s+)?"
    r"(?:turns?|revolutions?|rotations?|revs?)\b"
    r"|(?:(?<![\d.])\d+(?:\.\d+)?|π|\\pi|\bpi)\s*(?:rad|radians?)\b)"
    r"(?!\s*(?:/|per\b|each\b|every\b|an?\s+(?:second|minute|hour)\b))",
    re.IGNORECASE,
)
# The kinds of input a force's work is written with.
_FORCE_OR_WORK = frozenset({"newton", "joule"})
_ENERGY_OR_POWER = frozenset({"joule", "watt"})

_FROM_HORIZONTAL = word_pattern(angle_to(r"horizontal\b"))
_FROM_VERTICAL = word_pattern(angle_to(r"vertical\b"))
# A motion said to be up or down: the words the lifting laws' bindings read ("raise",
# "lift", "hoist", "climb"), and "vertically".
_VERTICAL_MOTION = re.compile(
    r"\b(?:rais(?:e|es|ed|ing)|lift(?:s|ed|ing)?|hoist(?:s|ed|ing)?|ascend(?:s|ed|ing)?"
    r"|climb(?:s|ed|ing)?|vertically|straight\s+up)\b",
    re.IGNORECASE,
)
# A motion said to be along the level: "horizontally", "along the floor", "a level road".
_LEVEL_MOTION = re.compile(
    r"\b(?:horizontally|along\s+(?:a|an|the)\s+(?:level\s+|horizontal\s+|flat\s+)?"
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
    """The question's angle is measured from the horizontal while the motion is vertical,
    or from the vertical while the motion is along the level: it is no angle between the
    force and the displacement."""
    from_horizontal = _FROM_HORIZONTAL.search(text)
    if from_horizontal is not None:
        rest = text[: from_horizontal.start()] + " " + text[from_horizontal.end() :]
        if _VERTICAL_MOTION.search(rest) is not None:
            return True
    from_vertical = _FROM_VERTICAL.search(text)
    if from_vertical is not None:
        rest = text[: from_vertical.start()] + " " + text[from_vertical.end() :]
        return _LEVEL_MOTION.search(rest) is not None
    return False
