"""Which optical element a question is about, and which signs its distances carry, however it
is worded.

A convex mirror and a concave lens diverge: their focal lengths and images carry the sign
the New Cartesian convention gives them, and a law written for a converging element
certifies the wrong one. "10 cm from a convex mirror of focal length 15 cm" was certified
30 cm (the image is 6 cm behind the mirror), and so was "a convex spherical mirror" and
"The mirror is convex" once the first was fixed by its words alone (2026-10-30). A myopic
eye's lens, a minus lens, a rear-view mirror and an erect, diminished image name one too:
each was certified as converging (2026-11-01).

The unsigned laws read every distance as a real one. A question that writes a sign
("u = -15 cm"), calls a distance negative, or puts the image on its virtual side ("30 cm
behind the mirror", "in front of the lens") states a convention they do not read: m = -v/u
certified -3 for an image 30 cm behind a concave mirror (it is +3).
"""

from __future__ import annotations

import re

# "biconcave" and "double-concave" too; a plane mirror beside a convex lens is no convex mirror.
_CONVEX = re.compile(r"convex\b")
_CONCAVE = re.compile(r"concave\b")
_MIRROR = re.compile(r"(?<!plane )\bmirrors?\b")
_LENS = re.compile(r"\blens(?:es)?\b")
_DIVERGING = re.compile(
    r"\bdiverging\b|\bvirtual\s+image\b|\bnegative\s+focal\b"
    r"|\b(?:negative|minus)\s+(?:lens|lenses|power)\b"
    # A short-sighted eye is corrected by a concave lens.
    r"|\bmyop|\b(?:short|near)[\s-]?sight"
    # A vehicle's or a shop's mirror that widens the view is convex.
    r"|\brear[\s-]?view\b"
    r"|\b(?:wing|side|side[\s-]?view|security|surveillance|blind[\s-]?spot|traffic|road)"
    r"\s+mirrors?\b"
)
# Only a diverging element forms an upright image smaller than the object.
_UPRIGHT = re.compile(r"\b(?:virtual|erect|upright)\b")
_DIMINISHED = re.compile(r"\b(?:diminished|smaller)\b")
_INVERTED = re.compile(r"\b(?:real|inverted|upside[\s-]?down)\b")
# "u = -15 cm" (a hyphen, a minus sign or a dash), "(+30 cm)": a sign on a number, not a
# range's dash ("10-15 cm").
_SIGNED_NUMBER = re.compile(r"(?<![\w.,)])[-+\u2212\u2013]\s?\d")
_SIGN_WORD = re.compile(r"\b(?:negative|minus)\b")
# The image's clause runs to the object's ("an image of an object placed 20 cm in front of
# it") or to its sentence's end; "the object's side" and "the side of the object" are the
# image's place.
_OBJECT_CLAUSE = r"(?<!side of the )(?<!side as the )\bobject\b(?!'?s\s+side)"
_IMAGE_CLAUSE = re.compile(
    rf"\bimage\b(?P<clause>(?:(?!{_OBJECT_CLAUSE}|[.?!;](?:\s|$)).)*)"
)
_BEHIND = re.compile(r"\bbehind\b|\b(?:other|opposite|far)\s+side\b|\bbeyond\b")
_IN_FRONT = re.compile(
    r"\bin\s+front\b|\b(?:same|near)\s+side\b|\bobject'?s\s+side\b"
    r"|\bside\s+(?:of|as)\s+the\s+object\b"
)
_LEFT_RIGHT = re.compile(r"\b(?:left|right)\s+of\b")


def diverging_element(text: str) -> bool:
    """A convex mirror, a concave lens or a diverging element, named in any order."""
    lower = text.lower()
    return bool(
        _DIVERGING.search(lower)
        or (_CONVEX.search(lower) and _MIRROR.search(lower))
        or (_CONCAVE.search(lower) and _LENS.search(lower))
        or (_UPRIGHT.search(lower) and _DIMINISHED.search(lower))
    )


def converging_element(text: str) -> bool:
    """A converging lens or mirror, a convex lens or a concave mirror, named in any order."""
    lower = text.lower()
    return bool(
        "converging" in lower
        or (_CONVEX.search(lower) and _LENS.search(lower))
        or (_CONCAVE.search(lower) and _MIRROR.search(lower))
    )


def upright_image(text: str) -> bool:
    """The image is called virtual, erect or upright."""
    return _UPRIGHT.search(text.lower()) is not None


def inverted_image(text: str) -> bool:
    """The image is called real or inverted, or forms on a real image's side."""
    lower = text.lower()
    return _INVERTED.search(lower) is not None or "real" in _image_sides(lower)


def signed_distances(text: str) -> bool:
    """The question gives a distance its sign: on a number, in words, or by putting the image
    on the side whose distance the conventions sign negative (or on a side it does not let
    us tell)."""
    lower = text.lower()
    return bool(
        _SIGNED_NUMBER.search(lower)
        or _SIGN_WORD.search(lower)
        or any(side != "real" for side in _image_sides(lower))
    )


def _image_sides(lower: str) -> list[str]:
    """Each side the question puts its image on: "real" behind a lens or in front of a
    mirror, "virtual" the other way, "unread" for a left or a right, for both sides at
    once, or for an element that is not one lens or one mirror."""
    lens, mirror = _LENS.search(lower) is not None, _MIRROR.search(lower) is not None
    sides: list[str] = []
    for found in _IMAGE_CLAUSE.finditer(lower):
        clause = found.group("clause")
        behind = _BEHIND.search(clause) is not None
        in_front = _IN_FRONT.search(clause) is not None
        if _LEFT_RIGHT.search(clause) or (behind and in_front):
            sides.append("unread")
        elif behind or in_front:
            sides.append("unread" if lens == mirror else "real" if behind == lens else "virtual")
    return sides
