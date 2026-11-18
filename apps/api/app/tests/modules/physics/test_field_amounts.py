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
    # The picture's own question only (the first text): never an earlier turn's numbers.
    assert [c.written for c in stated_charges([_NC, "charges of 7 nC"])] == ["3 nC", "2 nC"]
    assert stated_charges(["Draw it.", _NC]) == []
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


@pytest.mark.parametrize(
    "question",
    [
        "Draw the electric field lines around a negative charge of 2 nC.",
        "Draw the field lines of a 2 nC negative point charge.",
    ],
)
def test_a_charge_its_own_words_call_negative_is_negative(question: str) -> None:
    """ "a negative charge of 2 nC" was read +2 nC: a right minus block was refused and a wrong
    + block drew outward lines (Gemini, PR #2482)."""
    assert [charge.sign for charge in stated_charges([question])] == [-1]
    negative = _charges({"sign": "-", "amount": "2 nC"})
    positive = _charges({"sign": "+", "amount": "2 nC"})
    assert read_description(negative, [question]) is not None
    assert read_description(positive, [question]) is None


def test_each_charge_takes_the_sign_its_own_phrase_names() -> None:
    question = (
        "A positive charge of 3 nC and a negative charge of 2 nC are 4 cm apart. "
        "Draw the field lines."
    )
    assert [charge.sign for charge in stated_charges([question])] == [1, -1]


def test_a_test_charge_in_an_explanation_is_no_source() -> None:
    """ "the force on a positive test charge" after the request names no charge of the
    picture: one negative charge is drawn, a dipole refused (Gemini, PR #2482)."""
    question = (
        "Draw the field lines around a negative charge. Explain how the arrows show the "
        "force on a positive test charge."
    )
    assert read_description(_charges({"sign": "-"}), [question]) is not None
    assert read_description(_charges({"sign": "-"}, {"sign": "+"}), [question]) is None


def _plates(positive: str) -> str:
    return json.dumps({"kind": "field", "plates": {"positive": positive}})


def test_plates_are_drawn_only_for_a_question_that_names_them_as_it_charges_them() -> None:
    """A plates block under "a +3 nC charge" drew two plates (Claude, PR #2482)."""
    assert read_description(_plates("top"), ["Draw the field around a +3 nC charge."]) is None
    plates = "Draw the field between two parallel plates."
    assert read_description(_plates("top"), [plates]) is not None
    negative_top = "Draw the field between two parallel plates; the top plate is negative."
    assert read_description(_plates("top"), [negative_top]) is None
    assert read_description(_plates("bottom"), [negative_top]) is not None


def test_one_plural_sign_is_every_listed_charges() -> None:
    question = "Draw the field lines of two negative charges of 3 nC and 2 nC placed 4 cm apart."
    assert [charge.sign for charge in stated_charges([question])] == [-1, -1]


def test_a_test_charge_q_is_no_source() -> None:
    question = (
        "Draw the field lines around a charge +2q. Explain the force on a positive test charge q."
    )
    assert [charge.written for charge in stated_charges([question])] == ["2q"]


def test_an_earlier_turns_charges_are_not_the_pictures() -> None:
    """A 3.0 C / 2.0 C force problem, then "draw the pattern around a) a positive charge
    b) a negative charge": the picture is the line's (Gemini, PR #2482)."""
    texts = [
        "Draw the pattern of field lines around a) a positive charge b) a negative charge",
        "Two point charges of 3.0 C and 2.0 C are 5.0 m apart. Find the force.",
    ]
    part_a = json.dumps({"kind": "field", "part": "a", "charges": [{"sign": "+"}]})
    part_b = json.dumps({"kind": "field", "part": "b", "charges": [{"sign": "-"}]})
    assert read_description(part_a, texts) is not None
    assert read_description(part_b, texts) is not None
    # "draw it" after a setup it does not restate: nothing here can check its signs.
    after = ["draw it", "Two charges of +3 nC and -2 nC are 4 cm apart. Find the force."]
    plus = json.dumps({"kind": "field", "charges": [{"sign": "+"}]})
    assert read_description(plus, after) is None


def test_a_plural_sign_is_every_listed_q_multiples() -> None:
    """ "two negative point charges of 2q and q": both negative (Gemini, PR #2482)."""
    question = "Draw the field of two negative point charges of 2q and q placed 10 cm apart."
    assert [charge.sign for charge in stated_charges([question])] == [-1, -1]


def test_a_parts_picture_takes_only_its_own_charges() -> None:
    """ "a) a positive charge b) a +3 nC charge": part a states no amount, so its sign-only
    block stands; part a's block never takes part b's +3 nC (Gemini, PR #2482; Codex, PR
    #2490)."""
    question = "Draw the field lines around a) a positive charge b) a +3 nC charge."
    part_a = json.dumps({"kind": "field", "part": "a", "charges": [{"sign": "+"}]})
    taken = json.dumps({"kind": "field", "part": "a", "charges": [{"sign": "+", "amount": "3 nC"}]})
    part_b = json.dumps(
        {"kind": "field", "part": "b", "charges": [{"sign": "+", "amount": "3 nC"}]}
    )
    assert stated_charges([question], "a") == []
    assert [c.written for c in stated_charges([question], "b")] == ["3 nC"]
    assert read_description(part_a, [question]) is not None
    assert read_description(taken, [question]) is None
    assert read_description(part_b, [question]) is not None


@pytest.mark.parametrize(
    ("question", "part", "sign"),
    [
        (
            "2. Draw the pattern of the electric field around: a) a positive charge b) a "
            "negative charge. Explain what the arrows mean and explain at which points the "
            "strength of the field is greatest.",
            "b",
            "-",
        ),
        (
            "2. Draw the pattern of the electric field around: a) a positive charge b) a "
            "negative charge. Explain what the arrows mean.",
            "a",
            "+",
        ),
    ],
)
def test_a_colon_before_the_parts_keeps_their_signs(question: str, part: str, sign: str) -> None:
    """The GCSE prompt of field_sketch_replies.json lost its parts at the colon (Gemini,
    PR #2482)."""
    right = json.dumps({"kind": "field", "part": part, "charges": [{"sign": sign}]})
    wrong = json.dumps(
        {"kind": "field", "part": part, "charges": [{"sign": "+" if sign == "-" else "-"}]}
    )
    assert read_description(right, [question]) is not None
    assert read_description(wrong, [question]) is None


def test_parts_split_by_semicolons_keep_their_own_signs() -> None:
    question = (
        "Sketch the field lines for (a) two positive charges; (b) a positive and a negative charge."
    )
    pair = json.dumps({"kind": "field", "part": "a", "charges": [{"sign": "+"}, {"sign": "+"}]})
    dipole = json.dumps({"kind": "field", "part": "b", "charges": [{"sign": "+"}, {"sign": "-"}]})
    assert read_description(pair, [question]) is not None
    assert read_description(dipole, [question]) is not None


def test_each_parts_plates_are_charged_as_that_part_says() -> None:
    """ "when: a) the top plate is positive b) the top plate is negative" refused both
    parts, read against the whole prompt (Gemini, PR #2482)."""
    question = (
        "Draw the field between two parallel plates when: a) the top plate is positive "
        "b) the top plate is negative."
    )
    top = json.dumps({"kind": "field", "part": "a", "plates": {"positive": "top"}})
    bottom = json.dumps({"kind": "field", "part": "b", "plates": {"positive": "bottom"}})
    wrong = json.dumps({"kind": "field", "part": "b", "plates": {"positive": "top"}})
    assert read_description(top, [question]) is not None
    assert read_description(bottom, [question]) is not None
    assert read_description(wrong, [question]) is None


@pytest.mark.parametrize(
    "question",
    [
        "Draw the electric field pattern. One charge is positive and the other is negative.",
        "Show the electric field lines. One charge is positive and the other is negative.",
    ],
)
def test_signs_stated_after_the_request_are_held(question: str) -> None:
    """The cut after the request dropped "One charge is positive and the other is
    negative", so any signs passed (Gemini, PR #2482)."""
    dipole = json.dumps({"kind": "field", "charges": [{"sign": "+"}, {"sign": "-"}]})
    pair = json.dumps({"kind": "field", "charges": [{"sign": "+"}, {"sign": "+"}]})
    assert read_description(dipole, [question]) is not None
    assert read_description(pair, [question]) is None


def test_every_stated_charge_is_drawn_and_a_part_must_be_the_questions() -> None:
    """A lone +3 nC for "+3 nC and -2 nC" is another picture; on a lettered prompt a block
    naming no part, or one the question has not, draws nothing (Gemini, PR #2482)."""
    pair = "Draw the field lines around charges +3 nC and -2 nC."
    lone = _charges({"sign": "+", "amount": "3 nC"})
    both = _charges({"sign": "+", "amount": "3 nC"}, {"sign": "-", "amount": "2 nC"})
    assert read_description(lone, [pair]) is None
    assert read_description(both, [pair]) is not None
    parts = "Draw the field around: a) a positive charge b) a negative charge."
    no_part = json.dumps({"kind": "field", "charges": [{"sign": "+"}, {"sign": "-"}]})
    part_c = json.dumps({"kind": "field", "part": "c", "charges": [{"sign": "+"}]})
    part_a = json.dumps({"kind": "field", "part": "a", "charges": [{"sign": "+"}]})
    assert read_description(no_part, [parts]) is None
    assert read_description(part_c, [parts]) is None
    assert read_description(part_a, [parts]) is not None
