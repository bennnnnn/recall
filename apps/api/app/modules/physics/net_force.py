"""Whether the one force a question states is the whole net force on its body.

F = ma, m = F/a and a = F/m read a stated force as all the force there is. Beside a weight,
a lift's floor, friction that acts, a slope, a spring or a pull up against gravity it is not:
"60 N with μ = 0.2 gives 1 m/s²" was a 60 kg box for 20.3 kg, and a scale in a lift read
708.6 N was 354 kg for 60 kg (review 2026-11-12). A force the question calls the net one
("a net force of 20 N on a cart on a ramp") is all of it, whatever else acts.
"""

from __future__ import annotations

import re

from app.services.law_binding.ask import ask_clause
from app.services.law_binding.words import word_pattern

# A lift or an elevator: its floor or scale pushes with m(g ± a), so a reading there is
# neither the weight mg nor the net force ma (``lift_normal_force``). "Reads 708.6 N
# accelerating up at 2 m/s²" was m = F/a = 354 kg, and an apparent weight over that
# 2 m/s² as g the same, for 60 kg.
LIFT = ("elevator", "lift")
# The marker the binder's excludes read (``binding._with_markers``).
NOT_NET_FORCE_MARKER = "notnetforce"
# The marker for a lift the body rides in, which the weight's laws exclude.
IN_A_LIFT_MARKER = "inalift"
# The car, not the verb: an elevator, or "lift" in a noun phrase ("the lift", "in a
# stationary lift", "a 1000 kg lift accelerates") that no object follows. "A crane lifts a
# 200 kg crate" and "the workers lift the box" still weigh mg; read as a word prefix,
# "lifts" set the weight aside and the question declined.
_LIFT_CAR = re.compile(
    r"\belevator"
    r"|\b(?:a|an|the|this|its|his|her|their|our|my|same|in|inside|into)\s+"
    r"(?:[\w.\-]+\s+){0,3}?lifts?\b"
    r"(?!\s+(?:(?:a|an|the|it|them|him|her|his|their|its|up)\b|\d))"
)
# Forces that share the net force with one stated beside them.
_OTHER_FORCES = (
    "weigh",
    *LIFT,
    "frictional",
    "friction force",
    "force of friction",
    "with friction",
    "against friction",
    "rough",
    # A force up against gravity is m(g + a), not ma.
    "upward",
    "vertical",
    "raise",
    "raising",
    "hoist",
    "rocket",
    "launch",
    "normal force",
    "incline",
    "ramp",
    "slope",
    "pulley",
    "spring",
    "centripetal",
    "buoyan",
)
_NET_FORCE = re.compile(r"\b(?:net|resultant|unbalanced)\s+force\b")
# A coefficient of friction said as one: "μ = 0.2", "μk = 0.3", "a coefficient of kinetic
# friction of 0.3", "friction coefficient 0.25". A bare "coefficient of 0.47" may be a drag
# coefficient, and "5 μC" is a charge. Each run of space is read once (possessive): split
# between the \s* either side of an optional mark, "mu" and a run of spaces took quadratic time.
_STATED_MU_RE = re.compile(
    r"(?:coefficient\s+of\s+(?:kinetic\s+|static\s+)?friction|friction\s+coefficient"
    r"|(?:\bmu|\u03bc)(?:\s*+_?\s*+[ks\u2096\u209b])?)"
    r"\s*+(?:of|=|is)?\s*+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def friction_coefficients(text: str) -> tuple[tuple[int, float], ...]:
    """Each coefficient of friction the question states: where its number starts, and it."""
    return tuple((match.start(1), float(match.group(1))) for match in _STATED_MU_RE.finditer(text))


def states_net_force(lower: str) -> bool:
    """The question gives a force as the net one, outside what it asks."""
    clause = ask_clause(lower)
    asked_at = len(lower) if clause is None else lower.rfind(clause)
    asked_at = len(lower) if asked_at < 0 else asked_at
    return _NET_FORCE.search(lower, 0, asked_at) is not None


def friction_acts(lower: str) -> bool:
    """A coefficient of friction above zero is stated: μ = 0 says none acts."""
    return any(value > 0 for _start, value in friction_coefficients(lower))


def in_a_lift(lower: str) -> bool:
    """The body rides in a lift or an elevator, whose floor pushes with m(g ± a)."""
    return _LIFT_CAR.search(lower) is not None


def others_share_the_force(lower: str) -> bool:
    """Another force acts on the body beside the one stated, which is not called the net
    force."""
    if states_net_force(lower):
        return False
    return friction_acts(lower) or any(word_pattern(word).search(lower) for word in _OTHER_FORCES)
