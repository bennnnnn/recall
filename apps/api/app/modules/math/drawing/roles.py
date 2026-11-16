"""Which part of a shape a stated size is, as the question's words say.

"Radius 5 cm", "a height of 12 cm", "6 m wide", "8 m up the wall": a size the question names
belongs to that part and no other. Each part's words are read the one way the geometry
extractors read a measure (``match.dimensions``: its name, linking words, then the whole
number; or the number, its unit, then the name), so a slant height is never a height and
"radius ½ m and height 4 m" has no radius 4. A size named as an amount (a perimeter, a
circumference, a diagonal, an area, a volume) is no part's length, and the sizes of a
"respectively" list are left off, their order being the model's reading.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.modules.math.drawing.question import Question
from app.modules.math.figure.grounding import unit_name, written_numbers
from app.modules.math.match.dimensions import measures_after, measures_before

# Each part's word for its size: the names read before a number, and those read after one.
_WORDS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "radius": (("radius", "radii"), ("in radius",)),
    "diameter": (("diameter",), ("in diameter", "across")),
    "height": (("height",), ("high", "tall", "in height")),
    "depth": (("depth",), ("deep", "in depth")),
    "width": (("width", "breadth"), ("wide", "in width")),
    "length": (("length",), ("long", "in length")),
    "side": (("side", "sides", "edge", "edges"), ()),
    "slant": (("slant height", "slant"), ()),
    "foot": (("foot",), ("from the wall",)),
    "top": (("top",), ("up the wall",)),
}
# The amounts a size can be named as, none of them a part's length.
_AMOUNTS = ("perimeter", "circumference", "diagonal", "area", "volume", "surface", "capacity")

# Each part of ``shapes.FORMS`` and the word that names its size.
PART_ROLES = {
    "radius": "radius", "top_radius": "radius", "bottom_radius": "radius",
    "outer_radius": "radius", "surface": "radius", "diameter": "diameter",
    "height": "height", "outer_height": "height", "top": "top", "foot": "foot",
    "depth": "depth", "width": "width", "length": "length", "side": "side", "slant": "slant",
}  # fmt: skip

# Each part's usual letter: r for a radius, h for a height.
_LETTERS = {"radius": "r", "height": "h", "width": "w", "length": "l", "side": "s",
            "diameter": "d", "depth": "d", "slant": "l", "top": "h", "foot": "x"}  # fmt: skip
_SAME = 1e-9
_RESPECTIVELY = re.compile(r"\brespectively\b")
_SENTENCE_END = re.compile(r"[.;:?!](?:\s|$)")


def _is_unit(word: str) -> bool:
    return bool(unit_name(word)) or word in {"unit", "units"}


def named_sizes(role: str, question: Question) -> list[float]:
    """The sizes the question names as ``role`` ("radius 5 cm", "1.2 m in diameter")."""
    return _named_by(_WORDS[role], question)


def _named_by(words: tuple[tuple[str, ...], tuple[str, ...]], question: Question) -> list[float]:
    before, after = words
    return [
        value
        for text in question.texts
        for value in (
            *(v for word in before for v in measures_after(text, word)),
            *(v for word in after for v in measures_before(text, word, _is_unit)),
        )
    ]


def _respectively(question: Question) -> list[float]:
    """The sizes a "respectively" list gives: "radius and height 3 cm and 10 cm respectively"."""
    found: list[float] = []
    for text in question.texts:
        lower = text.lower()
        for mark in _RESPECTIVELY.finditer(lower):
            ends = [end.end() for end in _SENTENCE_END.finditer(lower, 0, mark.start())]
            chunk = lower[ends[-1] if ends else 0 : mark.start()]
            found += [float(written.value) for written in written_numbers(chunk)]
    return found


def _among(value: float, values: Iterable[float]) -> bool:
    return any(abs(value - other) <= _SAME * max(1.0, abs(value)) for other in values)


def stated_on(roles: set[str], value: float, all_roles: Iterable[str], question: Question) -> bool:
    """A stated size may stand on a part named by ``roles``: the question names that part
    with it, or names no part and no amount with it. ``all_roles``: the roles of the
    shape's other parts, whose own sizes it may not take."""
    if _among(value, _respectively(question)):
        return False
    own = [v for role in roles if role in _WORDS for v in _named_by(_WORDS[role], question)]
    if own:
        return _among(value, own)
    others = [
        v
        for role in set(all_roles) - roles
        if role in _WORDS
        for v in _named_by(_WORDS[role], question)
    ]
    return not _among(value, [*others, *_named_by((_AMOUNTS, ()), question)])


def usual_letter(part: str) -> str | None:
    """The letter a part of ``shapes.FORMS`` usually goes by ("r" for a radius)."""
    return _LETTERS.get(PART_ROLES.get(part, part))
