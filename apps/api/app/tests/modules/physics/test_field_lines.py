"""Electric field lines: a reply's description, checked, laid out and traced by the server.

The owner's GCSE set (2026-11-16): "Draw the pattern of the electric field around a) a
positive charge b) a negative charge", then two unlike charges, two negative charges and
two oppositely charged plates, came back as ASCII art. These hold the picture the server
draws instead: lines from + to -, as many as each charge's size, arrows along E, and the
neutral point between like charges.
"""

from __future__ import annotations

import json
import math
from typing import Any

import pytest

from app.modules.physics.field_lines.build import field_fences
from app.modules.physics.field_lines.describe import read_description
from app.modules.physics.field_lines.trace import CHARGE_RADIUS
from app.modules.physics.schemas import SimulationBlockSpec

_QUESTION = "Draw the pattern of the electric field around a positive and a negative charge."


def _spec(description: dict[str, Any], texts: tuple[str, ...] = (_QUESTION,)) -> dict[str, Any]:
    fences = field_fences([json.dumps(description)], texts)
    assert len(fences) == 1, description
    body = fences[0].removeprefix("```simulation\n").removesuffix("\n```")
    SimulationBlockSpec.model_validate_json(body)
    spec: dict[str, Any] = json.loads(body)
    assert spec["type"] == "field" and spec["title_key"] == "electric_field"
    return spec


def _charges(*signs: str, **extra: Any) -> dict[str, Any]:
    return {"kind": "field", "charges": [{"sign": sign} for sign in signs], **extra}


def _near(point: list[float], centre: list[float], within: float = CHARGE_RADIUS + 0.03) -> bool:
    return math.dist(point, centre) <= within


def _ends_on(spec: dict[str, Any], centre: list[float]) -> int:
    return sum(_near(line[-1], centre) for line in spec["field"]["lines"])


def _starts_on(spec: dict[str, Any], centre: list[float]) -> int:
    return sum(_near(line[0], centre) for line in spec["field"]["lines"])


def test_a_positive_charge_sends_its_lines_straight_out() -> None:
    spec = _spec(_charges("+", part="a"))
    field = spec["field"]
    assert field["part"] == "a" and field["charges"][0]["sign"] == 1
    centre = field["charges"][0]["at"]
    assert _starts_on(spec, centre) == len(field["lines"]) == 14
    for arrow in field["arrows"]:
        out = (arrow["at"][0] - centre[0], arrow["at"][1] - centre[1])
        assert out[0] * arrow["dx"] + out[1] * arrow["dy"] > 0.99 * math.hypot(*out)


def test_a_negative_charge_takes_its_lines_straight_in() -> None:
    spec = _spec(_charges("-", part="b"))
    field = spec["field"]
    centre = field["charges"][0]["at"]
    assert _ends_on(spec, centre) == len(field["lines"]) == 14
    for arrow in field["arrows"]:
        out = (arrow["at"][0] - centre[0], arrow["at"][1] - centre[1])
        assert out[0] * arrow["dx"] + out[1] * arrow["dy"] < 0


def test_unlike_charges_join_from_plus_to_minus() -> None:
    spec = _spec(_charges("+", "-"))
    plus, minus = (charge["at"] for charge in spec["field"]["charges"])
    joined = [
        line for line in spec["field"]["lines"] if _near(line[0], plus) and _near(line[-1], minus)
    ]
    assert len(joined) >= 6
    # Never the other way: no line runs from the negative charge to the positive one.
    assert not any(
        _near(line[0], minus) and _near(line[-1], plus) for line in spec["field"]["lines"]
    )
    assert spec["field"].get("neutral") is None


def test_two_like_charges_leave_a_neutral_point_between_them() -> None:
    spec = _spec(_charges("-", "-"))
    (neutral,) = spec["field"]["neutral"]
    assert neutral == pytest.approx([0.0, 0.0], abs=1e-3)
    left, right = (charge["at"] for charge in spec["field"]["charges"])
    # Every line ends on one of them: none starts on either.
    assert _starts_on(spec, left) == _starts_on(spec, right) == 0


def test_the_neutral_point_of_unequal_charges_is_nearer_the_smaller() -> None:
    """+4 μC and +1 μC two units apart: E is zero where d₁/d₂ = √(4/1) = 2."""
    question = "Draw the field lines around charges of +4 μC and +1 μC."
    spec = _spec(
        {
            "kind": "field",
            "charges": [{"sign": "+", "amount": "4 μC"}, {"sign": "+", "amount": "1 μC"}],
        },
        (question,),
    )
    left, right = (charge["at"][0] for charge in spec["field"]["charges"])
    (neutral,) = spec["field"]["neutral"]
    assert neutral[0] == pytest.approx(left + (right - left) * 2 / 3, abs=1e-3)
    labels = [charge["label"] for charge in spec["field"]["charges"]]
    assert labels == ["+4 μC", "+1 μC"]


def test_line_counts_follow_the_charges_sizes() -> None:
    question = "Sketch the field of a charge +2q near a charge -q."
    spec = _spec(
        {"kind": "field", "charges": [{"sign": "+", "amount": "2q"}, {"sign": "-", "amount": "q"}]},
        (question,),
    )
    big, small = (charge["at"] for charge in spec["field"]["charges"])
    # Seven lines end on -q, and +2q sends out about twice that: the lines joining the two
    # are drawn from -q's seven, and one of +2q's own runs past -q off the picture.
    assert _ends_on(spec, small) == 7
    assert 12 <= _starts_on(spec, big) <= 16
    assert [charge["label"] for charge in spec["field"]["charges"]] == ["+2q", "−q"]


def test_plates_have_parallel_lines_from_plus_to_minus() -> None:
    spec = _spec({"kind": "field", "part": "c", "plates": {"positive": "top"}})
    field = spec["field"]
    top, bottom = field["plates"]
    assert top["sign"] == 1 and bottom["sign"] == -1
    assert len(field["lines"]) == 9
    for line in field["lines"]:
        assert line[0][1] == pytest.approx(top["start"][1], abs=0.05)
        assert line[-1][1] == pytest.approx(bottom["start"][1], abs=0.05)
    # The middle lines are straight across the gap; the end ones fringe only a little.
    middle = field["lines"][4]
    assert max(abs(x - middle[0][0]) for x, _y in middle) < 0.01
    for line in field["lines"]:
        assert max(abs(x - line[0][0]) for x, _y in line) < 0.25
    assert all(arrow["dy"] < -0.9 for arrow in field["arrows"])


def test_a_lower_positive_plate_turns_the_field_up() -> None:
    spec = _spec({"kind": "field", "plates": {"positive": "bottom"}})
    assert all(arrow["dy"] > 0.9 for arrow in spec["field"]["arrows"])


@pytest.mark.parametrize(
    "description",
    [
        # A key the vocabulary does not hold: a place the row cannot put the charge.
        {"kind": "field", "charges": [{"sign": "+", "at": [0, 1]}, {"sign": "-"}]},
        {"kind": "field", "charges": [{"sign": "+"}] * 4},
        {"kind": "field", "charges": [], "plates": {"positive": "top"}},
        {"kind": "field", "charges": [{"sign": "+"}], "plates": {"positive": "top"}},
        {"kind": "field"},
        {"kind": "field", "plates": {"positive": "left"}},
        {"kind": "magnetic", "charges": [{"sign": "+"}]},
        # An amount the question does not state, amounts of two kinds, one charge without.
        {"kind": "field", "charges": [{"sign": "+", "amount": "5 μC"}]},
        {
            "kind": "field",
            "charges": [{"sign": "+", "amount": "2q"}, {"sign": "-", "amount": "4 μC"}],
        },
        {"kind": "field", "charges": [{"sign": "+", "amount": "2q"}, {"sign": "-"}]},
        # Too unequal for a line count to show: 1 line beside 14.
        {"kind": "field", "charges": [{"sign": "+", "amount": "8q"}, {"sign": "-", "amount": "q"}]},
        # Not charge.
        {"kind": "field", "charges": [{"sign": "+", "amount": "2 kg"}]},
    ],
)
def test_a_description_that_does_not_check_draws_nothing(description: dict[str, Any]) -> None:
    question = "Draw the field of charges +2q, -q, 4 μC and +8q."
    assert read_description(json.dumps(description), [question]) is None
    assert field_fences([json.dumps(description)], [question]) == []


def test_not_json_draws_nothing() -> None:
    assert field_fences(["(+) --> (-)", '{"kind": "field", "charges": ['], [_QUESTION]) == []


def test_several_parts_draw_a_picture_each_and_one_picture_once() -> None:
    blocks = [
        json.dumps(_charges("+", "-", part="a")),
        json.dumps(_charges("-", "-", part="b")),
        json.dumps({"kind": "field", "part": "c", "plates": {"positive": "top"}}),
        json.dumps(_charges("-", "-", part="b")),
    ]
    fences = field_fences(blocks, [_QUESTION])
    assert [json.loads(fence.split("\n")[1])["field"]["part"] for fence in fences] == [
        "a",
        "b",
        "c",
    ]


def test_every_line_stays_in_the_picture_and_within_the_schema() -> None:
    for description in (_charges("+", "-", "+"), _charges("-", "+", "-"), _charges("+", "+")):
        spec = _spec(description)
        for line in spec["field"]["lines"]:
            for x, y in line:
                assert spec["x_min"] - 1e-6 <= x <= spec["x_max"] + 1e-6
                assert spec["y_min"] - 1e-6 <= y <= spec["y_max"] + 1e-6
