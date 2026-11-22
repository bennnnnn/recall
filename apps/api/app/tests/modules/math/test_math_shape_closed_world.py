"""A shape reader claims a question only when it reads every word of it (``match/shape_words``).

The hard geometry rounds (2026-11-21) had shape readers answer questions about something else
drawn on their shape: the whole circle's 314.16 cm² as the checked card for a minor
segment's area (Q3), a 13-14-15 triangle's three angles for the length of an angle bisector
(Q7), and the bare circle, triangle or a 17 by 25 rectangle drawn under questions about a
chord, tangents, the incircle and the medians (Q2, Q5, Q21, Q31, Q34, Q36). A question that
names anything the reader does not model is the model's: a right answer left unchecked is
fine, a checked card for another question is not.
"""

from __future__ import annotations

import pytest

from app.modules.math.fence_conflict import contradicted_reading
from app.modules.math.match.shape_words import shape_call_answers
from app.modules.math.tool_check import tool_call_matches_user_text
from app.modules.math.tools.extract import extract_math_intent
from app.services.answer_check import (
    answer_of_another_kind,
    read_verified_value,
    stated_verdict,
)
from app.services.solving import VerifiedMathBlock


@pytest.mark.parametrize(
    "question",
    [
        # The live rounds, word for word.
        "A circle has a radius of 13 cm. A chord is 10 cm away from the center. Calculate the "
        "length of the chord.",
        "A circle has a radius of 10 cm. A chord subtends a central angle of 120°.\n\nFind the "
        "chord length and the area of the minor segment.",
        "Two tangents are drawn from an external point P to a circle. The radius is 7 cm, and "
        "the distance from P to the center is 25 cm.\n\nFind the length of each tangent.",
        "A triangle has sides 13 cm, 14 cm, and 15 cm. Find the length of the angle bisector "
        "drawn to the side of length 14 cm.",
        "A triangle has sides 13 cm, 14 cm, and 15 cm.\n\nCalculate:\na) Its area.\nb) Its "
        "inradius.\nc) Its circumradius.",
        "A triangle has side lengths 13 cm, 14 cm, and 15 cm.\n\nFind the distance from the "
        "incenter to the circumcenter.",
        "A triangle has sides of length 13 cm, 14 cm, and 15 cm.\n\nA circle is inscribed "
        "inside the triangle.\n\nFind the exact area of the circle and the exact area of the "
        "region inside the triangle but outside the circle.",
        "A triangle has side lengths 17 cm, 25 cm, and 28 cm.\n\nCalculate:\na) Its area.\nb) "
        "Its inradius.\nc) Its circumradius.\nd) The area of its incircle.",
        "A circle has a radius of 17 cm. Two parallel chords lie on opposite sides of the "
        "center, at distances of 8 cm and 12 cm from the center.\n\nFind the length of each "
        "chord and the distance between them.",
        "A triangle has side lengths 13 cm, 14 cm, and 15 cm.\n\nCalculate the lengths of all "
        "three medians using Apollonius's theorem.",
        # The same class in other words.
        "A triangle ABC has sides 13 cm, 14 cm and 15 cm. Find the area of triangle ABD.",
        "A triangle has sides 13 cm, 14 cm and 15 cm. Find the area of its inscribed circle.",
        "A triangle has sides 13 cm, 14 cm and 15 cm. A circle is drawn inside it touching all "
        "three sides. Find the area of the circle.",
        "A triangle has sides 13 cm, 14 cm and 15 cm. Find the length of the median to the "
        "side of length 14 cm.",
        "A triangle has sides 13 cm, 14 cm and 15 cm. Find the altitude to the side of length "
        "14 cm.",
        "A triangle has sides 13, 14 and 15. Find the length of the angle bisector from the "
        "largest angle.",
        "A circle has radius 10 cm. A tangent is drawn from a point 26 cm from the centre. Find "
        "the length of the tangent.",
        "A circle of radius 7 cm is inscribed in a square. Find the shaded area.",
        "A circle has a radius of 10 cm. Find the area of the sector and the segment.",
        "A circle has a radius of 10 cm. Find the length of a chord 6 cm from the centre.",
        "A rectangle is 8 cm by 6 cm. Find the area of the triangle formed by a diagonal.",
        "A square has side 10 cm. Find the radius of its circumscribed circle.",
        "A right triangle has legs 9 and 12. Find the altitude to the hypotenuse.",
        "A cone has radius 3 cm and height 4 cm. Find the volume of the largest sphere that "
        "fits inside it.",
        "A cube has side 4 cm. Find the length of its face diagonal.",
        "A trapezoid has bases 6 and 10 and height 4. Find the length of its midsegment.",
        "A garden is 8 m by 6 m. Find its diagonal.",
    ],
)
def test_shape_reader_declines_what_it_does_not_model(question: str) -> None:
    assert extract_math_intent(question) is None


@pytest.mark.parametrize(
    ("question", "kind"),
    [
        ("A circle has a radius of 10 cm. Find its area.", "circle"),
        ("A triangle has sides 13 cm, 14 cm and 15 cm. Find its area.", "triangle_sides"),
        ("A triangle has sides 3, 4 and 5. Find its angles.", "triangle_sides"),
        ("Draw a triangle with angles A=30, B=60, C=90", "triangle_sides"),
        ("Find the area and perimeter of a rectangle 3 cm by 4 cm.", "rectangle"),
        ("Find the angle made by the diagonal with the base of a rectangle 3 by 4", "rectangle"),
        (
            "Draw a circle of radius 4 cm with a chord of length 6 cm. How far is the chord from "
            "the centre?",
            "circle",
        ),
        ("Find the volume of a cylinder with radius 3 cm and height 10 cm.", "solid"),
        ("Find the hypotenuse of a right triangle with legs 5 cm and 12 cm.", "right_triangle"),
        ("What is the area of a trapezoid with bases 6 cm and 10 cm and height 4 cm?", "trapezoid"),
        ("Find the area of a sector with radius 6 cm and angle 60 degrees.", "sector"),
        ("Find the total surface area of a cube with side 4 m.", "solid"),
        ("area of a square with side 5 cm", "square"),
        ("a triangle has sides 3, 5 and 7. what is its largest angle?", "arithmetic"),
    ],
)
def test_shape_reader_keeps_what_it_reads_whole(question: str, kind: str) -> None:
    intent = extract_math_intent(question)
    assert intent is not None
    assert intent.kind == kind


@pytest.mark.parametrize(
    ("kind", "text", "whole"),
    [
        # Q31: the model's sympy call worked the triangle's 17 and 25 as a rectangle.
        (
            "rectangle",
            "A triangle has side lengths 17 cm, 25 cm, and 28 cm. Calculate its area.",
            False,
        ),
        ("rectangle", "Find the area of a rectangle 3 cm by 4 cm", True),
        ("circle", "A circle has a radius of 17 cm. Find the length of each chord.", False),
        ("circle", "What is the area of a circle of radius 5 cm?", True),
        # Q3: the circle's area worked as a step toward the minor segment's.
        (
            "circle",
            "A circle has a radius of 10 cm. A chord subtends a central angle of 120°. Find the "
            "chord length and the area of the minor segment.",
            False,
        ),
        # An everyday thing the model read as the shape: only what is asked is held.
        ("circle", "A circular garden has a radius of 7 m. What is its area?", True),
    ],
)
def test_a_shape_call_answers_only_what_its_shape_models(kind: str, text: str, whole: bool) -> None:
    assert shape_call_answers(kind, text) is whole


def test_a_tool_call_on_another_shape_is_no_match() -> None:
    q31 = "A triangle has side lengths 17 cm, 25 cm, and 28 cm. Calculate its area and inradius."
    assert not tool_call_matches_user_text(
        {"action": "rectangle", "width": 17, "height": 25}, [q31]
    )
    rectangle = "Find the area of a rectangle 3 cm by 4 cm"
    assert tool_call_matches_user_text(
        {"action": "rectangle", "width": 3, "height": 4}, [rectangle]
    )


_SEGMENT_REPLY = """**Required**
The area of the minor segment ($A_{seg}$)

**Solution**
$A_{seg} = A_{sector} - A_{triangle}$

**Answer**
$A_{seg} \\approx 61.42\\text{ cm}^2$
"""
_BISECTOR_REPLY = """**Solution**
$l_b = \\frac{3\\sqrt{65}}{2}$

**Answer**
$l_b = \\frac{3\\sqrt{65}}{2} \\approx 12.09\\text{ cm}$
"""
_CIRCLE_CARD = r"\approx 314.16\ \mathrm{cm}^{2}"
_ANGLES_CARD = r"\approx 53.1°, \approx 59.5°, \approx 67.4°"


def test_a_rounded_card_reads_as_its_value() -> None:
    circle = read_verified_value(_CIRCLE_CARD)
    angles = read_verified_value(_ANGLES_CARD)
    assert circle is not None and [float(n.value) for n in circle.numbers] == [314.16]
    assert angles is not None and [float(n.value) for n in angles.numbers] == [53.1, 59.5, 67.4]


@pytest.mark.parametrize(
    ("reply", "card", "another_kind"),
    [
        (_BISECTOR_REPLY, _ANGLES_CARD, True),  # a length under a card of angles
        (_SEGMENT_REPLY, _CIRCLE_CARD, False),  # both areas: the values disagree instead
        ("**Answer**\n$A = 50\\text{ cm}^2$", r"A = 50\ \mathrm{cm}^{2}", False),
        ("**Answer**\nThe angle is $30°$, opposite $5\\text{ cm}$", r"\approx 30°", False),
        ("**Answer**\n$T = 25°C$", r"\approx 30°", False),  # a temperature is no angle
        # Working after the Given section's blank line is the reply's own (review, #2523).
        (
            "**Given**\nr = 10 cm\n\nIts angles are $53.1°$, $59.5°$ and $67.4°$.\n\n"
            "**Answer**\n$l = 12\\text{ cm}$",
            _ANGLES_CARD,
            False,
        ),
    ],
)
def test_an_answer_of_another_kind_of_measure(reply: str, card: str, another_kind: bool) -> None:
    assert answer_of_another_kind(reply, card) is another_kind


@pytest.mark.parametrize(
    ("reply", "own", "card"),
    [
        (_SEGMENT_REPLY, r"A_{seg} \approx 61.42\ \text{cm}^2", _CIRCLE_CARD),
        (_BISECTOR_REPLY, r"l_b \approx 12.09\ \text{cm}", _ANGLES_CARD),
        # No card of the model's own: its Answer's value is the reply's.
        (_SEGMENT_REPLY, None, _CIRCLE_CARD),
    ],
)
def test_a_card_from_words_the_reply_contradicts_is_left_unchecked(
    reply: str, own: str | None, card: str
) -> None:
    """The backstop under the readers: Q3's circle area under the segment's 61.42 and Q7's
    angles under the bisector's 12.09 cm lose their check, and the reply keeps its own."""
    verified = VerifiedMathBlock(text="unused", canonical_answer=card, read_from_words=True)
    if own is not None:
        reply = f"{reply}\n```answer\n{own}\n```\n"
    unchecked = contradicted_reading(reply, verified, card)
    assert unchecked is not None
    assert "verified: true" not in unchecked
    assert card not in unchecked


def test_the_segment_reply_states_another_value() -> None:
    assert stated_verdict(_SEGMENT_REPLY, _CIRCLE_CARD) == "conflict"
