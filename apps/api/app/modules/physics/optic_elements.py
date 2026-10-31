"""Which optical element a question is about, however it is worded.

A convex mirror and a concave lens diverge: their focal lengths and images carry the sign
the New Cartesian convention gives them, and a law written for a converging element
certifies the wrong one. "10 cm from a convex mirror of focal length 15 cm" was certified
30 cm (the image is 6 cm behind the mirror), and so was "a convex spherical mirror" and
"The mirror is convex" once the first was fixed by its words alone (2026-10-30).
"""

from __future__ import annotations

import re

# "biconcave" and "double-concave" too; a plane mirror beside a convex lens is no convex mirror.
_CONVEX = re.compile(r"convex\b")
_CONCAVE = re.compile(r"concave\b")
_MIRROR = re.compile(r"(?<!plane )\bmirrors?\b")
_LENS = re.compile(r"\blens(?:es)?\b")
_DIVERGING = re.compile(r"\bdiverging\b|\bvirtual\s+image\b|\bnegative\s+focal\b")


def diverging_element(text: str) -> bool:
    """A convex mirror, a concave lens or a diverging element, named in any order."""
    lower = text.lower()
    return bool(
        _DIVERGING.search(lower)
        or (_CONVEX.search(lower) and _MIRROR.search(lower))
        or (_CONCAVE.search(lower) and _LENS.search(lower))
    )
