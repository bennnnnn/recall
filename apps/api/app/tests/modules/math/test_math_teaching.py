"""Typed teaching pictures stay tied to the verified answer."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.config import Settings
from app.modules.math.solve.teaching import build_teaching
from app.modules.math.solve.teaching_algebra import polynomial_division
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.extract import extract_math_intent


def _settings() -> Settings:
    return Settings()


def _block(text: str):
    intent = extract_math_intent(text)
    assert intent is not None
    block = _build_verified_block(intent, _settings())
    assert block is not None
    return intent, block


def _picture(block) -> dict[str, object]:
    pictures = [fence for fence in block.canonical_fences if fence.get("type") != "fraction"]
    assert pictures
    return pictures[-1]


@pytest.mark.parametrize(
    ("text", "kind", "answer"),
    [
        ("expanded form of 347", "place_value", "300 + 40 + 7"),
        ("place value of the 4 in 347", "place_value", "40"),
        ("base ten blocks for 347", "place_value", "300 + 40 + 7"),
        ("ten frame for 7 + 5", "ten_frame", "12"),
        ("array of 3 by 4", "array", "12"),
        ("3/4 on a number line", "fraction_line", r"\frac{3}{4}"),
        ("which is larger, 4.08 or 4.8", "decimal_compare", "4.8"),
        ("round 6.478 to the nearest hundredth", "rounding", "6.48"),
        ("round 1.25 to the nearest tenth", "rounding", "1.3"),
        ("round 147 to the nearest ten", "rounding", "150"),
        ("unit circle for 30 degrees", "unit_circle", None),
    ],
)
def test_closed_teaching_requests_keep_a_picture_and_an_answer(text, kind, answer):
    _intent, block = _block(text)
    picture = _picture(block)
    assert picture["type"] == kind
    if answer is None:
        assert picture["cosine"] in str(block.canonical_answer)
        assert picture["sine"] in str(block.canonical_answer)
    else:
        assert answer in str(block.canonical_answer)
    assert "grade" not in str(picture["speech"]).lower()
    reply = maybe_direct_math_reply(block, text)
    assert reply is not None
    assert "```arithmetic" in reply
    assert block.canonical_answer in reply


def test_seven_plus_five_uses_a_ten_frame_not_a_column():
    _intent, block = _block("7+5")
    picture = _picture(block)
    assert picture["type"] == "ten_frame"
    assert picture["make_ten"] is True
    assert picture["fill"] == 3
    assert picture["leftover"] == 2
    assert block.canonical_answer == "12"
    reply = maybe_direct_math_reply(block, "7+5")
    assert reply is not None and '"ten_frame"' in reply


@pytest.mark.parametrize(
    ("text", "equation", "value"),
    [
        ("1+1", "1 + 1 = 2", "2"),
        ("3+3", "3 + 3 = 6", "6"),
        ("3+4", "3 + 4 = 7", "7"),
        ("8 = 5 + 3", "5 + 3 = 8", "8"),
    ],
)
def test_a_single_digit_sum_is_one_forward_equation(text, equation, value):
    _intent, block = _block(text)
    assert block.canonical_answer == value
    assert block.display_answer == equation
    assert all(fence.get("type") != "number_bond" for fence in block.canonical_fences)
    reply = maybe_direct_math_reply(block, text)
    assert reply == f"```answer\n{equation}\n```\n"
    from app.modules.math.fence import validate_math_fences
    from app.modules.math.response_intent import classify_math_response_intent

    shown = validate_math_fences(
        reply or "",
        verified=replace(block, response_intent=classify_math_response_intent(text)),
    )
    assert shown.count("```answer") == 1
    assert equation in shown
    assert "number_bond" not in shown


def test_three_times_four_is_an_array():
    _intent, block = _block("3*4")
    picture = _picture(block)
    assert picture["type"] == "array"
    assert picture["rows"] == 3
    assert picture["columns"] == 4
    assert block.canonical_answer == "12"


def test_multidigit_addition_keeps_the_column_trace():
    _intent, block = _block("478+356")
    assert _picture(block)["type"] == "arithmetic"
    assert block.canonical_answer == "834"


def test_negative_addition_moves_on_a_number_line():
    _intent, block = _block("-3+5")
    picture = _picture(block)
    assert picture["type"] == "number_line_move"
    assert picture["start"] == -3
    assert picture["end"] == 2
    assert block.canonical_answer == "2"


def test_polynomial_and_synthetic_division_agree():
    text = "divide x^3-2x^2+4x-8 by x-2"
    _intent, block = _block(text)
    picture = _picture(block)
    assert picture["method"] == "long"
    assert picture["remainder"] == "0"
    synthetic = polynomial_division("x^3-2*x^2+4*x-8", "x-2", "synthetic")
    assert synthetic is not None
    assert synthetic.synthetic_bottom[-1] == "0"
    assert synthetic.quotient == picture["quotient"]
    reply = maybe_direct_math_reply(block, text)
    assert reply is not None and "grade" not in reply.lower()


def test_sin_30_keeps_its_value_and_shows_the_unit_circle():
    _intent, block = _block("sin(30 degrees)")
    assert block.canonical_answer == r"\frac{1}{2}"
    picture = _picture(block)
    assert picture["type"] == "unit_circle"
    assert picture["sine"] == block.canonical_answer
    reply = maybe_direct_math_reply(block, "sin(30 degrees)")
    assert reply is not None and r"\frac{1}{2}" in reply


def test_fraction_bars_use_the_common_denominator():
    _intent, block = _block("1/2 + 1/3")
    bars = [fence for fence in block.canonical_fences if fence.get("type") == "fraction_bar"]
    assert len(bars) == 1
    assert bars[0]["rows"][-1]["slots"] == 6
    assert block.canonical_answer


def test_quartiles_draw_the_same_five_number_summary():
    _intent, block = _block("quartiles of 1, 2, 3, 4, 5, 6, 7")
    plot = _picture(block)
    assert plot["type"] == "box_plot"
    assert block.canonical_answer == f"{plot['q1']}, {plot['median']}, {plot['q3']}"
    reply = maybe_direct_math_reply(block, "quartiles of 1, 2, 3, 4, 5, 6, 7")
    assert reply is not None and '"box_plot"' in reply


def test_fair_coin_tree_and_point_translation():
    _intent, block = _block("probability tree for a fair coin")
    tree = _picture(block)
    assert tree["type"] == "probability_tree"
    assert len(tree["branches"]) == 2
    _intent, moved = _block("translate the point (2, 3) by (3, -2)")
    shift = _picture(moved)
    assert shift["type"] == "transformation"
    assert shift["answer"] == "(5, 1)"


def test_incomplete_or_false_teaching_requests_are_declined():
    assert extract_math_intent("place value of 4 in 344") is None
    assert extract_math_intent("8 = 5 + 4") is None
    assert extract_math_intent("expanded form of 347 and tell me a joke") is None
    numeric = extract_math_intent("12 divided by 3")
    assert numeric is not None
    assert numeric.teaching_op is None
    assert numeric.school_op == "long_division"
    bare = extract_math_intent("divide 12 by 3")
    assert bare is None or bare.teaching_op is None
    assert build_teaching("histogram", "1,50") is None


def test_just_the_answer_hides_the_picture():
    text = "just the answer: 7+5"
    _intent, block = _block(text)
    reply = maybe_direct_math_reply(block, text)
    assert reply == "```answer\n12\n```\n"


def test_model_path_keeps_the_picture_unless_only_the_answer_was_requested():
    from app.modules.math.fence import validate_math_fences
    from app.modules.math.response_intent import classify_math_response_intent

    _intent, block = _block("7+5")
    shown = validate_math_fences(
        "Seven plus five is twelve.",
        verified=replace(block, response_intent=classify_math_response_intent("7+5")),
    )
    assert '"ten_frame"' in shown
    hidden = validate_math_fences(
        "12",
        verified=replace(
            block, response_intent=classify_math_response_intent("just the answer: 7+5")
        ),
    )
    assert "ten_frame" not in hidden
