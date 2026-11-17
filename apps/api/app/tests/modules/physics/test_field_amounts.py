"""A field picture's charges are the question's: each amount held to a stated charge, with
its unit and its sign (review of feat/field-lines).

"+3 nC and +2 nC" drawn as a + and a -, "4 nC" taken from "4 cm", μC passing for nC and any
"1" passing as stated were all drawn before; now each draws nothing.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.physics.field_lines.build import field_fences
from app.modules.physics.field_lines.describe import read_description
from app.modules.physics.field_lines.stated import stated_charges
from app.modules.physics.field_lines.trace import Box, PointCharge, Sources, neutral_points

_Q = "Sketch the electric field around a charge of +2q and a charge of -q placed 10 cm apart."
_NC = "Draw the field lines for charges +3 nC and +2 nC that are 4 cm apart."


def _charges(*charges: dict[str, Any]) -> str:
    return json.dumps({"kind": "field", "charges": list(charges)})


@pytest.mark.parametrize(
    ("description", "labels"),
    [
        # A signed amount, its sign read and held to the charge's.
        (_charges({"sign": "+", "amount": "+2q"}, {"sign": "-", "amount": "-q"}), ["+2q", "−q"]),
        (_charges({"sign": "+", "amount": "2q"}, {"sign": "-", "amount": "−q"}), ["+2q", "−q"]),
        (_charges({"sign": "+", "amount": "2q"}, {"sign": "-", "amount": "q"}), ["+2q", "−q"]),
    ],
)
def test_a_signed_amount_is_read(description: str, labels: list[str]) -> None:
    picture = read_description(description, [_Q])
    assert picture is not None and [c.label for c in picture.charges] == labels


@pytest.mark.parametrize(
    "description",
    [
        # Signs the question does not give: two positive charges drawn as + and -.
        _charges({"sign": "+", "amount": "3 nC"}, {"sign": "-", "amount": "2 nC"}),
        # An amount's own sign against its charge's.
        _charges({"sign": "+", "amount": "-3 nC"}, {"sign": "+", "amount": "2 nC"}),
        # Another unit, a distance read as a charge, an amount the question never states.
        _charges({"sign": "+", "amount": "3 μC"}, {"sign": "+", "amount": "2 μC"}),
        _charges({"sign": "+", "amount": "3 nC"}, {"sign": "+", "amount": "4 nC"}),
        _charges({"sign": "+", "amount": "3 nC"}, {"sign": "+", "amount": "1 nC"}),
        # The question sizes its charges, so the picture must say them.
        _charges({"sign": "+"}, {"sign": "+"}),
        # One stated charge drawn twice.
        _charges({"sign": "+", "amount": "3 nC"}, {"sign": "+", "amount": "3 nC"}),
    ],
)
def test_an_amount_the_question_does_not_state_draws_nothing(description: str) -> None:
    assert read_description(description, [_NC]) is None
    assert field_fences([description], [_NC]) == []


def test_the_stated_charges_are_the_questions_own() -> None:
    held = read_description(
        _charges({"sign": "+", "amount": "3 nC"}, {"sign": "+", "amount": "2 nC"}), [_NC]
    )
    assert held is not None and [c.label for c in held.charges] == ["+3 nC", "+2 nC"]
    # The first message that states charges, the user's last first: never another's numbers.
    assert [c.written for c in stated_charges(["Draw it.", _NC, "charges of 7 nC"])] == [
        "3 nC",
        "2 nC",
    ]
    # Sign only, when the question states no size.
    signs = read_description(
        _charges({"sign": "+"}, {"sign": "-"}), ["a positive and a negative charge"]
    )
    assert signs is not None and [c.q for c in signs.charges] == [1.0, -1.0]


def test_three_charges_keep_every_neutral_point_the_schema_holds() -> None:
    """Three charges in a row may have up to four zeros on the row: none is dropped, and
    the picture is never lost for one."""
    sources = Sources(
        charges=(
            PointCharge((-2.0, 0.0), 1.0),
            PointCharge((0.0, 0.0), 1.0),
            PointCharge((2.0, 0.0), 1.0),
        )
    )
    found = neutral_points(sources, Box(-3.7, 3.7, -1.7, 1.7))
    assert 1 <= len(found) <= 4
    fences = field_fences(
        [json.dumps({"kind": "field", "charges": [{"sign": "+"}] * 3})], ["three positive charges"]
    )
    assert len(fences) == 1


@pytest.mark.parametrize("amount", ["3e-9 C", "3 × 10⁻⁹ C", "+3e-9 C"])
def test_an_amount_in_scientific_notation_is_read_as_the_question_states_it(amount: str) -> None:
    """The amount and the question's charges are read by one reader: "3e-9 C" and
    "3 x 10^-9 C" are the question's own charge (PR #2482 re-review)."""
    question = "Draw the field lines of charges +3 × 10⁻⁹ C and +2 × 10⁻⁹ C."
    picture = read_description(
        _charges({"sign": "+", "amount": amount}, {"sign": "+", "amount": "2e-9 C"}), [question]
    )
    assert picture is not None and len(picture.charges) == 2
