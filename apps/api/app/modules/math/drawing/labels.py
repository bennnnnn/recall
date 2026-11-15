"""A label in a ```draw description, held to the question.

A label is one of three things, and anything else is left off its part:

- a value the question states, with its unit as the question writes it ("12 m"), held by
  ``figure.grounding`` (a rate, "2 cm/min", states no length, and "r = 3 cm" no size when
  the question ties r to another letter, "h = 3r");
- a letter the question or the reply's working names ("r", "h", "x", "θ");
- a whole multiple of such a letter ("2r"), shown only when the figure's own shape makes it
  true (a window's width is twice its radius) or the question writes it ("h = 3r").

No label is a number the question does not state: an optimisation's answer, a computed
distance or the size at one instant of a related-rates problem is the reply's to give.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from fractions import Fraction

from app.modules.math.drawing.question import Question
from app.modules.math.figure.drawing import angle_label, length_label
from app.modules.math.figure.grounding import states_angle, states_length, unit_name

_VALUE = re.compile(r"^(\d+(?:\.\d+)?)\s*([A-Za-z]*)\.?$")
_ANGLE = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:°|º|deg|degrees?)$")
_TERM = re.compile(r"^(\d+(?:\.\d+)?)?\s*\*?\s*([A-Za-z\u0391-\u03c9])([\u2032']?)$")
_NO_UNIT = frozenset({"unit", "units", "u"})


@dataclass(frozen=True)
class Label:
    """A label as drawn, with what it says: a stated length (``value`` in ``unit``), or a
    letter times ``coefficient`` (``written``: the question writes that term)."""

    text: str
    value: float | None = None
    unit: str = ""
    letter: str | None = None
    coefficient: Fraction = Fraction(1)
    written: bool = False


def read_length(text: str, question: Question) -> Label | None:
    """A part's label, or None when it is none the question allows. A letter named with
    its value ("h = 3r", "r = 5 cm") says what the value does, on the same terms."""
    text = " ".join(text.split())
    name, equals, rest = text.partition("=")
    if equals:
        return _named(name.strip(), rest.strip(), text, question)
    if not text:
        return None
    value = _VALUE.match(text)
    # "10 units" names no unit of length: it is the bare 10. "2r" is a multiple of r.
    written_unit = "" if value is None or value.group(2).lower() in _NO_UNIT else value.group(2)
    if value is not None and (not written_unit or unit_name(written_unit)):
        number, unit = float(value.group(1)), unit_name(written_unit)
        changing = Fraction(number).limit_denominator(10_000) in question.changing
        if number <= 0 or changing or not states_length(list(question.numbers), number, unit):
            return None
        return Label(length_label(number, unit), value=number, unit=unit)
    term = _TERM.match(text)
    if term is None:
        return None
    letter = term.group(2) + term.group(3).replace("'", "\u2032")
    if letter not in question.letters:
        return None
    coefficient = Fraction(term.group(1)) if term.group(1) else Fraction(1)
    if coefficient <= 0:
        return None
    shown = letter if coefficient == 1 else f"{_coefficient(coefficient)}{letter}"
    written = f"{coefficient}{term.group(2)}" in question.terms
    return Label(shown, letter=letter, coefficient=coefficient, written=written)


def _named(name: str, rest: str, text: str, question: Question) -> Label | None:
    """ "h = 3r": the question writes that relation; "r = 5 cm": a stated value of r."""
    said = read_length(rest, question) if "=" not in rest else None
    letter = read_length(name, question)
    if said is None or letter is None or letter.letter is None or letter.coefficient != 1:
        return None
    if said.value is None and _spaced(text) not in {_spaced(t) for t in question.relations}:
        return None
    if said.value is not None and not _its_value(letter.letter, said.value, question):
        return None
    return replace(said, text=f"{letter.text} = {said.text}")


def _its_value(letter: str, value: float, question: Question) -> bool:
    """A value named by a letter is that letter's where the question gives letters values:
    never another letter's ("r = 12 cm" beside "h = 12 cm")."""
    exact = Fraction(value).limit_denominator(10_000)
    mine = {given for name, given in question.assigned if name == letter}
    others = {given for name, given in question.assigned if name != letter}
    return exact in mine if mine else exact not in others


def _spaced(text: str) -> str:
    return "".join(text.split()).lower()


def read_angle(text: str, question: Question, size: float) -> str | None:
    """An angle mark's label: a letter, or a stated size that is the angle's own."""
    text = " ".join(text.split())
    if not text:
        return None
    value = _ANGLE.match(text)
    if value is not None:
        degrees = float(value.group(1))
        held = states_angle(list(question.numbers), degrees) and abs(degrees - size) < 0.05
        return angle_label(degrees) if held else None
    term = read_length(text, question)
    return term.text if term is not None and term.letter and term.coefficient == 1 else None


def _coefficient(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{float(value):g}"
