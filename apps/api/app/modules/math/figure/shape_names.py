"""The words a question names a shape by: a refusal, never a choice.

A model reads which shape a question asks to see; these words only refuse a picture of a
shape where the question names another one, or names it something more specific. Round 3
(2026-11-14) drew a cone for "the frustum of a right circular cone", and a circle card for
"the sphere whose equation is (x - 1)^2 + (y + 2)^2 + z^2 = 1": a default shape in the place
of the stated one. A question that names no shape at all ("a tin can", "a pizza", "a ball")
leaves the model's reading standing: an everyday thing is drawn as the solid it is. A word
matches at its start ("cylind" in "cylindrical"), so "semicircle" names no circle.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_CONE = ("cone", "conical")
_NOT_A_CONE = ("frustum", "frusta", "truncated")
_SPHERE = ("sphere", "spherical")
# The words that leave a box or a can without its lid, and those that give it one.
_OPEN = ("open box", "open-top", "open top", "open at the top", "no lid", "without a lid", "no top",
         "without a top", "lidless", "open cylind", "open can", "open tank")  # fmt: skip
_CLOSED = ("closed", "with a lid", "has a lid", "top and bottom", "lid and base")

# Each shape: the words one of which names it, and the words that say it is something else.
NAMES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "cone": (_CONE, _NOT_A_CONE),
    "frustum": (("frustum", "frusta", "truncated cone"), ()),
    "cylinder": (("cylind",), ()),
    "sphere": (_SPHERE, ("hemispher",)),
    "hemisphere": (("hemispher",), ()),
    "circle": (("circle", "circular"), (*_SPHERE, "cylind", *_CONE)),
    "window": (("window",), ()),
    "rectangle": (("rectang", "oblong"), ()),
    "square": (("square",), ()),
    "box": (("box", "cuboid", "rectangular prism", "container", "crate", "room", "cube"), ()),
    # A box drawn with its lid, whatever the question calls it ("a fish tank"): never for one
    # it leaves open (round 3's c047 drew a closed cuboid for "an open box").
    "closed_box": ((), _OPEN),
    "sheet": (("corner",), ()),
    "ladder": (("ladder",), ()),
}


# "Square" in a unit or a root names no square: "a pizza of 100 square inches".
_AS_UNIT = re.compile(
    r"\bsquare\s+(?:root|units?|cm|mm|m|km|ft|feet|foot|in|inch(?:es)?|yards?|miles?"
    r"|(?:centi|milli|kilo)?met(?:re|er)s?)\b"
)


def _said(words: str, stem: str) -> bool:
    return re.search(rf"\b{re.escape(stem)}", words) is not None


def _names(words: str, shape: str) -> bool:
    return any(_said(words, stem) for stem in NAMES[shape][0])


_SOLID_SHAPES = ("cone", "frustum", "cylinder", "sphere", "hemisphere", "box")


def names_a_solid(texts: Iterable[str]) -> bool:
    """The texts name a solid: a cone, a frustum, a cylinder, a sphere or a box (a cube)."""
    words = " ".join(texts).lower()
    return any(_names(words, shape) for shape in _SOLID_SHAPES)


def names_shape(texts: Iterable[str], shape: str) -> bool:
    """Nothing the texts name says the shape is another one: they name ``shape`` or no
    shape at all, and none of its "unless" words."""
    found = NAMES.get(shape)
    if found is None:
        return True
    stems, unless = found
    words = " ".join(texts).lower()
    if any(_said(words, stem) for stem in unless):
        return False
    if not stems or any(_said(words, stem) for stem in stems):
        return True
    rest = _AS_UNIT.sub(" ", words)
    return not any(_names(rest, other) for other in NAMES if other != shape)


def lid_said(texts: Iterable[str]) -> bool | None:
    """What the texts say of a lid: True for one ("a closed can", or nothing said: a box or
    a can is closed unless it is said to be open), False for none ("an open box"), None when
    they say both."""
    words = " ".join(texts).lower()
    left_open = any(_said(words, stem) for stem in _OPEN)
    closed = any(_said(words, stem) for stem in _CLOSED)
    return None if left_open and closed else not left_open
