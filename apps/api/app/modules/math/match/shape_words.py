"""The words a shape reading accounts for: a shape reader claims a question only when it
reads every word of it.

A shape reader takes a shape's printed measures and computes that shape's own quantities
(a circle's area, a triangle's angles). It found its shape and a quantity's name anywhere in
the question, so a question about something else drawn on the shape was answered as the
shape: "A circle has a radius of 10 cm. A chord subtends a central angle of 120°. Find the
chord length and the area of the minor segment." had the whole circle's 314.16 cm² as its
checked card (asked: 61.42), and "A triangle has sides 13 cm, 14 cm, and 15 cm. Find the
length of the angle bisector drawn to the side of length 14 cm." its three angles (asked:
3√65/2) (2026-11-21, hard geometry round).

So the reading is held to a closed world, not to a list of words it must not meet: each word
of the question is a word of asking or of presentation (find, the, rounded, draw), a unit,
the reader's own shape, a measure that reader reads or computes, a letter given a value
("r = 5"), or a vertex of the shape it names (AB in "triangle ABC"). Any other word (a
bisector, a segment, an inradius, an inscribed circle, triangle ABD inside triangle ABC, a
garden) is something the reading does not model, and the question is the model's. A right
answer left unchecked is fine; a checked card for another question is not.
"""

from __future__ import annotations

import re

from app.modules.math.match.asked_quantities import asking_spans
from app.modules.math.match.measure_relations import another_shape_named
from app.modules.math.schemas import MathIntent

# Asking, linking and presentation: words that change nothing a shape's card computes.
_GLUE = frozenset(
    """
    a an the this that these those its it their each both all every any one two three four
    i me we us you your my our they them
    of with and or to in on at for from by as if then also
    whose which where who has have had having is are was were be been being
    measures measuring measure measured equal equals given let suppose about including
    include includes made makes between
    find calculate compute determine work out what whats how much give state evaluate
    estimate tell need want know please can could would will do does get solve value
    values answer answers working steps step method formula using use show
    round rounded rounding nearest decimal decimals place places dp significant sig figs
    figures digits digit tenth tenths hundredth hundredths whole number approximately
    approx
    draw sketch diagram picture figure label labelled labeled illustrate visualize
    visualise
    """.split()
)
# Length, area and volume units, and the angle's.
_UNITS = frozenset(
    """
    cm mm m km in inch inches ft foot feet yd yard yards mi mile miles
    meter meters metre metres centimeter centimeters centimetre centimetres
    millimeter millimeters millimetre millimetres kilometer kilometers kilometre kilometres
    unit units degree degrees deg
    """.split()
)
# "square centimetres", "cubic metres", "sq ft": a unit, never the shape ("a square in a
# circle" is a square).
_UNIT_POWER = re.compile(
    r"\b(?:square|sq|cubic|cu)\.?\s+(?=(?:"
    + "|".join(sorted(_UNITS - {"in"}, key=len, reverse=True))
    + r")\b)",
    re.IGNORECASE,
)
_CIRCLE = frozenset("circle circles radius radii diameter area circumference".split())
# A chord the circle reader read, and the distance from the centre it computes.
_CHORD = frozenset("chord length distance centre center far".split())
_TRIANGLE = frozenset("triangle triangles side sides length lengths".split())
_PLANE_MEASURES = frozenset("area perimeter".split())
_ANGLES = frozenset("angle angles".split())
# A solid's measures, and each solid by the words that name it (a cylinder's base is a circle).
_SOLID_MEASURES = frozenset(
    """
    closed total surface area volume capacity radius diameter height side sides edge edges
    length width breadth depth base dimensions slant
    """.split()
)
_SOLIDS: dict[str, frozenset[str]] = {
    "cube": frozenset({"cube"}),
    "rectangular_prism": frozenset("cuboid box rectangular prism rect".split()),
    "cylinder": frozenset({"cylinder", "circle"}),
    "cone": frozenset({"cone", "circle", "right", "circular"}),
    "sphere": frozenset({"sphere", "ball"}),
    "pyramid": frozenset("pyramid square based rectangular".split()),
}
# Every reading's words by the kind it reads (a solid's are its own).
_KIND_WORDS: dict[str, frozenset[str]] = {
    "circle": _CIRCLE,
    "sector": frozenset(
        "sector sectors circle pie slice radius angle central area arc length major minor".split()
    ),
    "rectangle": frozenset(
        "rectangle rectangles rect length width breadth height base side sides dimensions by"
        " x diagonal diagonals long wide".split()
    )
    | _PLANE_MEASURES
    | _ANGLES,
    "square": frozenset("square squares side sides edge length diagonal diagonals".split())
    | _PLANE_MEASURES,
    "trapezoid": frozenset(
        "trapezoid trapezoids trapezium trapeziums base bases parallel side sides top bottom"
        " height area".split()
    )
    | _ANGLES,
    "parallelogram": frozenset("parallelogram parallelograms base height side sides".split())
    | _PLANE_MEASURES
    | _ANGLES,
    "right_triangle": _TRIANGLE
    | _PLANE_MEASURES
    | _ANGLES
    | frozenset("right angled legs leg base height hypotenuse".split()),
    "triangle_sides": _TRIANGLE | _PLANE_MEASURES | _ANGLES | frozenset({"right", "angled"}),
    "triangle": frozenset("triangle triangles base height area".split()) | _ANGLES,
}
# The nouns that name each reading's shape: a reading claims a question that names it.
_SHAPE_NOUNS: dict[str, frozenset[str]] = {
    "circle": frozenset({"circle"}),
    "sector": frozenset({"sector", "pie"}),
    "rectangle": frozenset({"rectangle", "rect", "oblong"}),
    "square": frozenset({"square"}),
    "trapezoid": frozenset({"trapezoid", "trapezium"}),
    "parallelogram": frozenset({"parallelogram"}),
    "right_triangle": frozenset({"triangle"}),
    "triangle_sides": frozenset({"triangle"}),
    "triangle": frozenset({"triangle"}),
}
# Part labels of a multi-part question: "a)", "(b)", "(ii)".
_PART_LABEL = re.compile(r"(?<![\w(])\(?(?:[a-h]|i{1,3}|iv|vi{0,3})\)", re.IGNORECASE)
_WORD = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)?")
# A letter set to a value is a given's name: "r = 5", "a: 3".
_NAMED_VALUE = re.compile(r"\s*[=:]")
# "3 x 4", "8 by 5": the times sign between two measures.
_TIMES = re.compile(r"(?<=\d)\s*x\s*(?=\d)", re.IGNORECASE)
# A shape named by its vertices: "triangle ABC", "rectangle PQRS".
_VERTICES = re.compile(
    r"\b(?:triangle|rectangle|square|parallelogram|trapezoid|trapezium|quadrilateral)"
    r"\s+([A-Z]{3,4})\b"
)


def _words_of(intent: MathIntent) -> frozenset[str]:
    if intent.kind == "solid":
        solid = _SOLIDS.get(intent.solid_shape or "")
        return _SOLID_MEASURES | solid if solid is not None else frozenset()
    words = _KIND_WORDS.get(intent.kind)
    if words is None:
        return frozenset()
    if intent.kind == "circle" and intent.chord_length is not None and _chord_read(intent):
        return words | _CHORD
    if intent.kind == "triangle_sides" and intent.triangle_relative_lengths:
        # A triangle read by its angles: its sides are no given, only relative.
        return words | frozenset({"interior"})
    return words


def _chord_read(intent: MathIntent) -> bool:
    """The circle reader works a chord's distance from the centre, or draws the chord; a
    chord it read and computes nothing of was another number ("a chord 10 cm away from
    the center": its length was asked)."""
    return bool(intent.wants_center_distance) or intent.school_op == "geometry_draw"


def unread_shape_words(intent: MathIntent, text: str) -> list[str]:
    """The words of ``text`` the shape reading ``intent`` does not account for, in order;
    empty when it reads every word (and for a reading that is no shape's)."""
    own = _words_of(intent)
    return unread_words(text, own) if own else []


def unread_words(text: str, own: frozenset[str]) -> list[str]:
    """The words of ``text`` that are neither a reader's ``own`` (in the singular or the
    plural), nor glue, a unit, a letter given a value or a vertex of the one shape the
    question names by its vertices, in order."""
    text = _PART_LABEL.sub(" ", _UNIT_POWER.sub(" ", _TIMES.sub(" by ", text)))
    # The vertices of the one shape the question names by them; a second name ("triangle
    # ABD" in triangle ABC) is another shape, and no letter is the read shape's.
    names = set(_VERTICES.findall(text))
    vertices = set(next(iter(names))) if len(names) == 1 else set()
    unread: list[str] = []
    for match in _WORD.finditer(text):
        raw = re.sub(r"['\u2019]s$", "", match.group())
        word = raw.lower()
        if word in _GLUE or word in _UNITS or word in own or word.removesuffix("s") in own:
            continue
        if len(word) == 1 and _NAMED_VALUE.match(text, match.end()):
            continue  # "r = 5", "A = 30"
        if raw.isupper() and set(raw) <= vertices:
            continue  # AB, BC and CA of triangle ABC
        unread.append(word)
    return unread


def shape_call_answers(kind: str, text: str) -> bool:
    """A model's call to compute a plane shape (the sympy tool's rectangle, square or circle)
    answers ``text``: the question names no other plane shape, and its asking sentences ask
    nothing the shape does not model. The model read which shape an everyday thing is ("a
    circular garden"), so the statements may describe it in any words; what is asked may
    not: a triangle's 17 and 25 worked as a rectangle drew that rectangle under the
    triangle's area, inradius and circumradius (2026-11-21, Q31)."""
    own = _KIND_WORDS.get(kind)
    if own is None or another_shape_named(text, kind):
        return False
    asked = " ".join(text[start:end] for start, end in asking_spans(text))
    return not unread_words(asked, own)


def _named(text: str, nouns: frozenset[str]) -> bool:
    """``text`` names the shape by one of its ``nouns`` (in the singular or the plural), not
    as a unit ("square centimetres")."""
    said = {word.lower().removesuffix("s") for word in _WORD.findall(_UNIT_POWER.sub(" ", text))}
    return not nouns.isdisjoint(said)


def reads_whole_question(intent: MathIntent, text: str) -> bool:
    """The shape reading ``intent`` accounts for every word of ``text``, and the text names
    its shape by its noun: no rectangle is read from a "17 cm by 25 cm" that names none. A
    reading that is no shape's is not judged here."""
    if intent.kind == "solid":
        # The solid readers find their solid by its name (``classify_solid_shape``).
        return not unread_shape_words(intent, text)
    nouns = _SHAPE_NOUNS.get(intent.kind)
    if nouns is None:
        return True
    return _named(text, nouns) and not unread_shape_words(intent, text)
