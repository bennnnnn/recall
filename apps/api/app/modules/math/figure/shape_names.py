"""The words a question names a shape by: a refusal, never a choice.

A model reads which shape a question asks to see; these words only refuse a picture of a
shape the question does not name, or of one it names something more specific than. Round 3
(2026-11-14) drew a cone for "the frustum of a right circular cone", and a circle card for
"the sphere whose equation is (x - 1)^2 + (y + 2)^2 + z^2 = 1": a default shape in the place
of the stated one. A word matches at its start ("cylind" in "cylindrical"), so "semicircle"
names no circle.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_CONE = ("cone", "conical")
_NOT_A_CONE = ("frustum", "frusta", "truncated")
_SPHERE = ("sphere", "spherical")

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
    "sheet": (("corner",), ()),
    "ladder": (("ladder",), ()),
}


def _said(words: str, stem: str) -> bool:
    return re.search(rf"\b{re.escape(stem)}", words) is not None


def names_shape(texts: Iterable[str], shape: str) -> bool:
    """The texts name ``shape``, and nothing they name says it is another shape."""
    found = NAMES.get(shape)
    if found is None:
        return True
    stems, unless = found
    words = " ".join(texts).lower()
    return any(_said(words, stem) for stem in stems) and not any(
        _said(words, stem) for stem in unless
    )
