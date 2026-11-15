"""Which part a stated size is, and what a stated amount measures, read from the question."""

from __future__ import annotations

import pytest

from app.modules.math.drawing.amounts import read_amount
from app.modules.math.drawing.question import read_question
from app.modules.math.drawing.roles import stated_on
from app.modules.math.match.dimensions import measures_after, measures_before


def test_measures_before_reads_a_size_named_after_it() -> None:
    def unit(word: str) -> bool:
        return word in {"m", "cm"}

    text = "A box is 8 cm long, 6 cm wide; it reaches 8 m up the wall; 8 apples long."
    assert measures_before(text, "long", unit) == [8.0]
    assert measures_before(text, "wide", unit) == [6.0]
    assert measures_before(text, "up the wall", unit) == [8.0]
    assert measures_after("radius 3 cm, then radius 5 cm", "radius") == [3.0, 5.0]


@pytest.mark.parametrize(
    ("question", "roles", "value", "held"),
    [
        ("A cone has slant height 13 cm and radius 5 cm.", {"height"}, 13, False),
        ("A cone has slant height 13 cm and radius 5 cm.", {"slant"}, 13, True),
        ("A square has a perimeter of 20 cm.", {"side"}, 20, False),
        ("A rectangle is 3 m wide with perimeter 30 m.", {"width"}, 3, True),
        ("A rectangle is 3 m wide with perimeter 30 m.", {"height"}, 30, False),
        ("Its radius and height are 3 cm and 10 cm respectively.", {"radius"}, 3, False),
        ("A 20 cm by 30 cm sheet.", {"length"}, 30, True),
        ("A tank of radius 2 m and height 5 m is 3 m deep.", {"height"}, 3, False),
    ],
)
def test_a_stated_size_goes_on_its_own_part(
    question: str, roles: set[str], value: float, held: bool
) -> None:
    every = ("radius", "height", "slant", "side", "width", "length", "depth")
    assert stated_on(roles, value, every, read_question([question], "")) is held


@pytest.mark.parametrize(
    ("question", "kind", "text", "amount"),
    [
        ("A can must hold 500 cm³.", "volume", "500 cm³", (500.0, "cm")),
        # The question's unit says what the amount is, never the description's.
        ("A can must hold 500 cm³.", "surface", "500 cm²", None),
        ("There is 12 m of framing.", "area", "12 m²", None),
        ("There is 12 m of framing.", "perimeter", "12 m", (12.0, "m")),
        ("A 10-litre can.", "volume", "10 litres", (10000.0, "cm")),
        # A bare number says no unit: unsure.
        ("It has an area of 48.", "area", "48", None),
    ],
)
def test_an_amount_is_what_the_question_measures_it_as(
    question: str, kind: str, text: str, amount: tuple[float, str] | None
) -> None:
    assert read_amount(kind, text, read_question([question], "")) == amount
