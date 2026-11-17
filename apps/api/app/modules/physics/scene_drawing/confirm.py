"""What the question's words must say for a scene to be drawn: confirmed, never assumed.

A scene draws one setup one way: a launch above the horizontal, a block sliding down its
slope, a body moving into one at rest, a converging lens, a string, light from air or from
the medium named first. Each property a word decides is drawn only when the question says
it in a phrasing recognised beside its value ("at 30° above the horizontal", "a 30° incline",
"a 2 kg cart moving at 3 m/s", "a converging lens", "a string 1.2 m long", "from air into
glass", "600 km above the Earth"). Any other phrasing draws nothing: a phrasing the server
does not know is never drawn as the default. ``guards`` refuses what these let through.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping

from app.modules.physics.scene_drawing.values import Stated
from app.services.law_binding.givens import Given

Confirm = Callable[[Stated, Mapping[str, Given], Mapping[str, float]], bool]

_I = re.IGNORECASE
# Words that set an angle's reference, or contradict one, in its sentence.
_REFERENCE = re.compile(
    r"\b(?:horizontal(?:ly)?|vertical(?:ly)?|below|beneath|depression|downwards?|upwards?|"
    r"plane|axis|normal|surface|boundary|interface|face|slope|incline|inclined|ramp|"
    r"north|south|east|west|perpendicular|parallel|wall)\b",
    _I,
)
_FROM_HORIZONTAL = re.compile(r"^\s*(?:above|to|with|from)\s+the\s+horizontal\b", _I)
_ELEVATION = re.compile(r"\bangle\s+of\s+elevation\s+(?:of\s+|is\s+)?$", _I)
_AGAINST_ABOVE = re.compile(r"\b(?:vertical(?:ly)?|below|beneath|depression|downwards?)\b", _I)
_HORIZONTALLY = re.compile(r"\bhorizontally\b", _I)
_LAUNCH_PLACE = re.compile(
    r"^\s*(?:high\s+|tall\s+)?(?:cliff|table|tower|building|bench|ledge|platform|bridge|"
    r"roof|balcony|window|desk)\b",
    _I,
)
_LAUNCH_HEIGHT = re.compile(r"\b(?:from|at)\s+(?:a\s+)?height\s+of\s+(?:about\s+)?$", _I)
# A slope's angle: "a 30° incline", "inclined at 25°", "an incline at 35 degrees".
_SLOPE_AFTER = re.compile(r"^[\s-]*(?:inclined\s+plane|incline|slope|ramp|hill|plane)\b", _I)
_SLOPE_BEFORE = re.compile(
    r"\b(?:inclined|tilted|incline|slope|ramp|plane|hill)\s+(?:at|of)\s+"
    r"(?:an\s+angle\s+of\s+)?$",
    _I,
)
_DOWN_SLOPE = re.compile(
    r"\b(?:slides?|sliding|slid|moves?|moving|accelerates?|accelerating)\s+down\b|"
    r"\breleased\b|\bstarts?\s+from\s+rest\b|\bplaced\b|\blet\s+go\b",
    _I,
)
_BANK = re.compile(
    r"\bbanked\s+(?:at\s+)?(?:an\s+angle\s+of\s+)?$|\bbank\s+angle\s+(?:of\s+|is\s+)?$", _I
)
# A body's speed straight after its own mass phrase: "a 2 kg cart moving at 3 m/s".
_OWN_SPEED = re.compile(
    r"^\s*(?:[a-z-]+\s+){1,3}?(?:(?:that\s+is\s+|which\s+is\s+|is\s+|initially\s+)?"
    r"(?:moving|travell?ing|rolling|sliding|going|heading|coasting)"
    r"(?:\s+(?:to\s+the\s+(?:right|left)|forward|along\s+[a-z]+))?\s+)?"
    r"(?:at|with\s+a\s+(?:speed|velocity)\s+of)\s*$",
    _I,
)
_REST_BEFORE = re.compile(r"\b(?:stationary|motionless|parked)\s+$", _I)
_REST_AFTER = re.compile(
    r"^\s*(?:[a-z-]+\s+){1,3}?(?:that\s+is\s+|which\s+is\s+|is\s+|initially\s+)?"
    r"(?:at\s+rest|stationary|resting|motionless)\b",
    _I,
)
_STICKS = re.compile(
    r"\b(?:stick|sticks|stuck|lock|locks|locked|embed\w*|coupl\w*|combine|together|"
    r"perfectly\s+inelastic)\b",
    _I,
)
_ELASTIC = re.compile(r"(?<!in)\belastic(?:ally)?\b", _I)
_INELASTIC = re.compile(r"\binelastic", _I)
_PULLEY = re.compile(r"\b(?:pulley|atwood)\b", _I)
_PENDULUM = re.compile(r"\bpendulum\b", _I)
_FLAT_SPRING = re.compile(r"\bhorizontal(?:ly)?\b|\b(?:table|surface|floor|track)\b", _I)
_STRING = re.compile(r"\b(?:string|wire|cord)s?\b", _I)
_LENS = re.compile(r"\b(?:converging|(?:bi-?)?convex)\s+(?:thin\s+|glass\s+)?lens\b", _I)
_FOCAL_BEFORE = re.compile(r"\bfocal\s+length\s+(?:of\s+|is\s+|=\s*)?$", _I)
_FOCAL_AFTER = re.compile(r"^\s*focal\s+length\b", _I)
_OBJECT = re.compile(r"\b(?:object|candle|arrow|pin)\b", _I)
_IMAGE = re.compile(r"\bimage\b", _I)
_TALL = re.compile(r"^\s*(?:tall|high)\b", _I)
_INCIDENCE_BEFORE = re.compile(
    r"\b(?:angle\s+of\s+incidence|incidence\s+angle|incident\s+angle)\s+(?:of\s+|is\s+|=\s*)?$"
    r"|\bincident\s+at\s+$",
    _I,
)
_FROM_NORMAL = re.compile(r"^\s*(?:to|from|with)\s+the\s+normal\b", _I)
_FROM_AIR = re.compile(r"\b(?:from|in|through)\s+(?:the\s+)?(?:air|a\s+vacuum|vacuum)\b", _I)
_FROM_INTO = re.compile(r"\bfrom\b", _I)
_INTO = re.compile(r"\b(?:into|enters?)\b", _I)
_ABOVE = re.compile(r"^\s*above\b", _I)
_ALTITUDE = re.compile(r"\b(?:altitude|height)\s+(?:of\s+)?(?:about\s+)?$", _I)
_EARTH = re.compile(r"\bearth\b", _I)
_ORBITED = re.compile(
    r"\b(?:orbits?|orbiting|around|round|above|circles?|circling)\s+(?:the\s+|a\s+)?"
    r"(?:planet\s+)?([a-z]+)",
    _I,
)
_OTHER_BODIES = frozenset(
    "moon mars jupiter sun venus saturn mercury neptune uranus pluto planet star titan "
    "europa io asteroid comet".split()
)


def _launch_angle(stated: Stated, angle: Given) -> bool:
    """ "at 30° above the horizontal", "an angle of elevation of 30°", or a bare "at 30°"
    in a sentence with no other reference word."""
    sentence = stated.sentence(angle)
    if _AGAINST_ABOVE.search(sentence):
        return False
    if _FROM_HORIZONTAL.search(stated.after(angle)) or _ELEVATION.search(stated.before(angle)):
        return True
    return _REFERENCE.search(sentence) is None


def _projectile(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    speed, angle, height = held.get("speed"), held.get("angle"), held.get("height")
    if angle is not None and not _launch_angle(stated, angle):
        return False
    if angle is None and (speed is None or not _HORIZONTALLY.search(stated.sentence(speed))):
        return False
    if height is not None:
        launched = _LAUNCH_PLACE.search(stated.after(height)) or _LAUNCH_HEIGHT.search(
            stated.before(height)
        )
        if not launched:
            return False
    return True


def _incline(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    """A slope's angle, a block said to slide down it, and kinetic friction too weak to
    hold it (μ < tan θ: a block that does not slide is no sliding scene)."""
    angle, mu = held["angle"], held["friction"]
    if not (_SLOPE_AFTER.search(stated.after(angle)) or _SLOPE_BEFORE.search(stated.before(angle))):
        return False
    if "vertical" in stated.sentence(angle).lower() or not _DOWN_SLOPE.search(stated.text):
        return False
    return angle.si is not None and mu.value < math.tan(angle.si)


def _banked(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    return _BANK.search(stated.before(held["angle"])) is not None


def _moving(stated: Stated, mass: Given, speed: Given) -> bool:
    """``speed`` written straight after ``mass``'s phrase: "a 2 kg cart moving at 3 m/s"."""
    if speed.start <= mass.start:
        return False
    return _OWN_SPEED.search(stated.text[stated.after_at(mass) : speed.start]) is not None


def _at_rest(stated: Stated, mass: Given) -> bool:
    return bool(
        _REST_BEFORE.search(stated.before(mass, 24)) or _REST_AFTER.search(stated.after(mass))
    )


def _collision(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    """Each speed after its own body's mass, the other body at rest or given its own speed
    the same way; the claim the words make ("they stick", "elastic")."""
    if not _moving(stated, held["mass1"], held["speed1"]):
        return False
    second = held.get("speed2")
    if second is None and not _at_rest(stated, held["mass2"]):
        return False
    if second is not None and not _moving(stated, held["mass2"], second):
        return False
    if flags.get("elastic") == 1.0:
        return _ELASTIC.search(stated.text) is not None and not _INELASTIC.search(stated.text)
    return _STICKS.search(stated.text) is not None


def _refraction(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    """An angle of incidence named so, or measured to the normal; light from air into the
    material, or from the medium named first into the one named second."""
    angle, into, came = held["angle"], held["index"], held.get("index_from")
    if not (
        _INCIDENCE_BEFORE.search(stated.before(angle)) or _FROM_NORMAL.search(stated.after(angle))
    ):
        return False
    if came is None:
        air = _FROM_AIR.search(stated.text)
        return air is not None and air.end() <= into.start
    if came.start > into.start or not _FROM_INTO.search(stated.before(came)):
        return False
    return _INTO.search(stated.text[came.end : into.start]) is not None


def _lens(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    """A lens named converging, its focal length named so, the object's distance and height
    in a sentence about the object and not its image."""
    focal, distance = held["focal_length"], held["object_distance"]
    if _LENS.search(stated.text) is None:
        return False
    if not (_FOCAL_BEFORE.search(stated.before(focal)) or _FOCAL_AFTER.search(stated.after(focal))):
        return False
    for given in (distance, held.get("object_height")):
        if given is None:
            continue
        sentence = stated.sentence(given)
        if not _OBJECT.search(sentence) or _IMAGE.search(sentence):
            return False
    height = held.get("object_height")
    return height is None or _TALL.search(stated.after(height)) is not None


def _orbit(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    """A height above the planet; Earth's own mass and radius only when the orbit's
    sentence names Earth and no other body is named as orbited, else both stated."""
    altitude = held["altitude"]
    if not (_ABOVE.search(stated.after(altitude)) or _ALTITUDE.search(stated.before(altitude))):
        return False
    if "planet_mass" in held and "planet_radius" in held:
        return True
    orbited = {word.lower() for word in _ORBITED.findall(stated.text)}
    if orbited & _OTHER_BODIES:
        return False
    return _EARTH.search(stated.sentence(altitude)) is not None


def _atwood(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    return _PULLEY.search(stated.text) is not None


def _pendulum(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    return _PENDULUM.search(stated.text) is not None


def _spring(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    """Drawn lying flat: only when the words put it so ("horizontal", "on a table")."""
    return _FLAT_SPRING.search(stated.text) is not None


def _standing(stated: Stated, held: Mapping[str, Given], flags: Mapping[str, float]) -> bool:
    """A string or wire, never a pipe's air column."""
    return _STRING.search(stated.text) is not None


CONFIRMS: dict[str, Confirm] = {
    "projectile": _projectile,
    "incline": _incline,
    "collision": _collision,
    "refraction": _refraction,
    "lens": _lens,
    "spring": _spring,
    "pendulum": _pendulum,
    "atwood": _atwood,
    "orbit": _orbit,
    "standing_wave": _standing,
    "banked_curve": _banked,
}
