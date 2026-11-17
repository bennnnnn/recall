"""What each scene cannot carry, read off the question: then it is not drawn.

A scene draws one setup in one way: a block sliding down its slope, a projectile launched
above the horizontal, two bodies on a line moving the same way, a converging lens, a spring
lying flat. The description cannot say otherwise, so when the question's words state a
direction, an angle's reference or an apparatus the scene does not draw, beside its values
("8 m/s up a 30° incline", "30° below the horizontal", "60° to the vertical", "30° with the
surface", "a diverging lens", "hangs on a spring", "head-on"), nothing is drawn. A refusal
is always safe; a picture of the opposite motion never is.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping

from app.modules.physics.scene_drawing.values import Stated
from app.services.law_binding.givens import Given

Guard = Callable[[Stated, Mapping[str, Given]], bool]

_SLOPE = r"(?:incline|slope|ramp|plane|hill)"
_UP_SLOPE = re.compile(rf"\bup\b[^.;]{{0,30}}?\b{_SLOPE}\b", re.IGNORECASE)
_STATIC = re.compile(r"\bstatic\b|μ_?s\b|\bmu_?s\b", re.IGNORECASE)
_CONNECTED = re.compile(r"\b(?:pulley|string|rope|cord|hanging|connected)\b", re.IGNORECASE)
# An angle not measured up from the horizontal: below it, or from the vertical.
_NOT_ABOVE = re.compile(
    r"\bbelow\b|\bdownwards?\b|\b(?:to|from|with)\s+the\s+vertical\b|\bvertically\b",
    re.IGNORECASE,
)
# An angle measured from the surface, not from the normal.
_FROM_SURFACE = re.compile(
    r"\b(?:to|from|with|and)\s+the\s+(?:glass\s+|water\s+)?"
    r"(?:surface|boundary|interface|horizontal|face)\b|\bglancing\b|\bgrazing\b",
    re.IGNORECASE,
)
# Light coming from a medium the description gives no index for: "from water into glass".
_FROM_MEDIUM = re.compile(
    r"\bfrom\s+(?:the\s+)?(?!air\b|vacuum\b)[a-z]+\b[^;?!]{0,40}?\b(?:into|enters?|to)\b",
    re.IGNORECASE,
)
# Two moving bodies the words put on one line, the same way.
_SAME_WAY = re.compile(
    r"\bsame\s+direction\b|\bfrom\s+behind\b|\bcatch(?:es)?\s+up\b|\bovertak|\brear-?ends?\b",
    re.IGNORECASE,
)
_HEAD_ON = re.compile(
    r"\bhead[- ]on\b|\bopposite\s+directions?\b|\btowards?\s+each\s+other\b|-\s*\d", re.IGNORECASE
)
_SIDES = re.compile(r"\b(east|west|north|south|left|right)\b", re.IGNORECASE)
_CONVERGING = re.compile(r"\b(?:converging|convex)\b", re.IGNORECASE)
_DIVERGING = re.compile(r"\b(?:diverging|concave)\b", re.IGNORECASE)
_FROM = re.compile(r"\bfrom\b", re.IGNORECASE)
_INTO = re.compile(r"\b(?:into|enters?|to)\b", re.IGNORECASE)
_HANGING = re.compile(r"\b(?:hang|hangs|hanging|hung|vertical|vertically|suspended)\b", re.I)
_LAUNCH = re.compile(r"\b(?:launch\w*|fires?|fired|shoots?|projects?)\b", re.IGNORECASE)
_CIRCLE = re.compile(r"\b(?:circle|circular|conical|cone)\b", re.IGNORECASE)
_MASSIVE_PULLEY = re.compile(r"\b(?:radius|dis[ck]|inertia|cylinder|wheel)\b", re.IGNORECASE)
_EARTH = re.compile(r"\bearth\b", re.IGNORECASE)


def _projectile(stated: Stated, held: Mapping[str, Given]) -> bool:
    """Launched above the horizontal: an angle below it, or from the vertical, anywhere in
    its sentence ("at an angle to the vertical of 60°") is another launch."""
    angle = held.get("angle")
    return angle is not None and _NOT_ABOVE.search(stated.sentence(angle)) is not None


def _incline(stated: Stated, held: Mapping[str, Given]) -> bool:
    """One block sliding down, from kinetic friction: never up, never held by static
    friction, never tied over a pulley to another."""
    text = stated.text
    return any(p.search(text) is not None for p in (_UP_SLOPE, _STATIC, _CONNECTED))


def _collision(stated: Stated, held: Mapping[str, Given]) -> bool:
    """Both on one line, the same way, the first catching the second: never head-on, never
    named opposite sides, never a second body running away from the first."""
    if _HEAD_ON.search(stated.text) is not None or _HANGING.search(stated.text) is not None:
        return True  # head-on, or a block hanging on a string that swings up (a pendulum)
    if len({side.lower() for side in _SIDES.findall(stated.text)}) > 1:
        return True
    first, second = held.get("speed1"), held.get("speed2")
    if first is None or second is None:
        return False
    # Both moving: the words must say they go the same way, the first the faster.
    return _SAME_WAY.search(stated.text) is None or (first.si or 0.0) <= (second.si or 0.0)


def _refraction(stated: Stated, held: Mapping[str, Given]) -> bool:
    """An angle of incidence from the normal, from the medium named first into the one
    named second; one measured from the surface, or media in an order the words do not
    say, is not drawn."""
    angle = held.get("angle")
    if angle is not None and _FROM_SURFACE.search(stated.sentence(angle)) is not None:
        return True
    into, came = held.get("index"), held.get("index_from")
    if into is None:
        return False
    if came is None:
        # From air: the words name no other medium the light comes from.
        return _FROM_MEDIUM.search(stated.text) is not None
    if came.start > into.start:
        return True
    before = stated.text[max(0, came.start - 40) : came.start]
    between = stated.text[came.end : into.start]
    return _FROM.search(before) is None or _INTO.search(between) is None


def _lens(stated: Stated, held: Mapping[str, Given]) -> bool:
    text = stated.text
    return _CONVERGING.search(text) is None or _DIVERGING.search(text) is not None


def _spring(stated: Stated, held: Mapping[str, Given]) -> bool:
    """A mass oscillating on a flat spring: never one hanging from it, never a launch."""
    return _HANGING.search(stated.text) is not None or _LAUNCH.search(stated.text) is not None


def _pendulum(stated: Stated, held: Mapping[str, Given]) -> bool:
    """A bob swinging in a plane: never one going round in a circle."""
    return _CIRCLE.search(stated.text) is not None


def _atwood(stated: Stated, held: Mapping[str, Given]) -> bool:
    """An ideal pulley: one with a radius, a disk's mass or inertia is another machine."""
    return _MASSIVE_PULLEY.search(stated.text) is not None


def _orbit(stated: Stated, held: Mapping[str, Given]) -> bool:
    """Round Earth unless the question gives the planet's own mass."""
    return "planet_mass" not in held and _EARTH.search(stated.text) is None


def _none(stated: Stated, held: Mapping[str, Given]) -> bool:
    return False


GUARDS: dict[str, Guard] = {
    "projectile": _projectile,
    "incline": _incline,
    "collision": _collision,
    "refraction": _refraction,
    "lens": _lens,
    "spring": _spring,
    "pendulum": _pendulum,
    "atwood": _atwood,
    "orbit": _orbit,
    "standing_wave": _none,
    "banked_curve": _none,
}
