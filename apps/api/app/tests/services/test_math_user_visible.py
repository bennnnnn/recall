"""Question → extract kind → canonical_answer / inject text. No LLM."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services import math_school, math_text_match, math_tools
from app.services.math_tools.extract import extract_math_intent
from app.services.tool_loop import turn_needs_tool_loop

_SETTINGS = Settings(math_tools_enabled=True, mcp_tool_loop_enabled=True)


def _block(question: str):
    intent = extract_math_intent(question)
    assert intent is not None, question
    block = math_tools._build_verified_block(intent, _SETTINGS)
    assert block is not None, question
    return intent, block


@pytest.mark.parametrize(
    "question, kind",
    [
        ("what is 1+1", "arithmetic"),
        ("7*8", "arithmetic"),
        ("3*4+2", "arithmetic"),
    ],
)
def test_bare_arithmetic_extracts_and_skips_tool_loop(question: str, kind: str) -> None:
    intent, block = _block(question)
    assert intent.kind == kind
    assert block.canonical_answer is not None
    assert turn_needs_tool_loop(question, has_verified_math=True, settings=_SETTINGS) is False


def test_bare_arithmetic_answers() -> None:
    assert _block("what is 1+1")[1].canonical_answer == "2"
    assert _block("7*8")[1].canonical_answer == "56"
    assert _block("3*4+2")[1].canonical_answer == "14"


def test_quadratic_discriminant_parenthesizes_negative_b() -> None:
    intent, block = _block("solve x^2-5x+6=0")
    assert intent.kind == "equation"
    assert "(-5)^{2}" in block.text
    assert "-5^{2}" not in block.text
    assert "2" in (block.canonical_answer or "")
    assert "3" in (block.canonical_answer or "")


def test_sin_1_5_answer_is_short_decimal() -> None:
    _intent, block = _block("sin(1.5)")
    answer = block.canonical_answer or ""
    assert len(answer) <= 40
    assert "." in answer


def test_derivative_of_sin_2x_is_calculus_not_trig() -> None:
    intent, block = _block("derivative of sin(2x)")
    assert intent.kind == "calculus"
    assert intent.operation == "differentiate"
    answer = (block.canonical_answer or "").replace(" ", "")
    assert "2" in answer
    assert "cos" in answer.lower()


def test_integrate_x_squared_dx_strips_differential() -> None:
    intent, block = _block("integrate x^2 dx")
    assert intent.kind == "calculus"
    assert intent.operation == "integrate"
    assert intent.expr == "x^2"
    answer = (block.canonical_answer or "").replace(" ", "")
    assert "x^{3}" in answer or "x^3" in answer
    assert "/3" in answer or "frac{x" in answer


def test_differentiate_e_to_x() -> None:
    intent, block = _block("differentiate e^x")
    assert intent.kind == "calculus"
    answer = (block.canonical_answer or "").lower()
    assert "e" in answer or "exp" in answer


def test_sin_pi_is_zero() -> None:
    _intent, block = _block("sin(pi)")
    answer = (block.canonical_answer or "").replace(" ", "")
    assert answer in {"0", "0.0"}


def test_solve_fahrenheit_for_celsius_has_no_re_im_soup() -> None:
    intent, block = _block("solve F = 9/5*C + 32 for C")
    assert intent.kind == "equation"
    assert intent.variable.lower() == "c"
    answer = block.canonical_answer or ""
    assert "re(" not in answer
    assert "im(" not in answer
    assert "C" in answer or "c" in answer


def test_solve_for_trailing_variable() -> None:
    intent, block = _block("solve d = r*t for t")
    assert intent.kind == "equation"
    assert intent.variable == "t"
    assert "t" in (block.canonical_answer or "")


def test_percent_uses_number_immediately_before_percent() -> None:
    intent, block = _block("Out of 250 people, what is 30% of 80?")
    assert intent.kind == "arithmetic"
    assert block.canonical_answer == "24"


def test_sector_arc_length_not_area() -> None:
    intent, block = _block("arc length of a sector with radius 5 and 60°")
    assert intent.kind == "sector"
    assert intent.wants_area is False
    answer = float(block.canonical_answer or "0")
    assert abs(answer - 5.236) < 0.05
    assert abs(answer - (25 * 3.14159 / 6)) > 1  # not the area ~13.09


def test_projectile_cliff_range_is_not_vacuum() -> None:
    intent, block = _block(
        "A projectile is launched at 20 m/s at 30 degrees from a 10 m cliff. What is its range?"
    )
    assert intent.kind == "projectile"
    assert intent.physics_params is not None
    assert intent.physics_params.get("h0") == 10.0
    answer = float((block.canonical_answer or "0").split()[0])
    assert abs(answer - 35.31) > 5
    assert abs(answer - 48.0) < 1.5


def test_average_speed_is_not_mean() -> None:
    intent, block = _block("average speed 120 km in 2 hours")
    assert intent.kind == "arithmetic"
    assert float(block.canonical_answer or "0") == 60.0


def test_convert_32_f_to_c_string_is_zero() -> None:
    intent, block = _block("convert 32 F to C")
    assert intent.kind == "unit"
    assert block.canonical_answer == "0"
    assert math_school.convert_unit(32.0, "F", "C") == "0"


def test_verified_inject_is_delimited_data_only() -> None:
    _intent, block = _block("7*8")
    assert "[BEGIN VERIFIED MATH]" in block.text
    assert "[END VERIFIED MATH]" in block.text
    assert "COPYING" not in block.text
    assert "Couldn't verify" not in block.text
    assert "SymPy" not in block.text


def test_complex_decision_is_not_symbolic_math() -> None:
    assert math_text_match.needs_symbolic("help me think through a complex decision") is False
    assert math_text_match.needs_symbolic("write me a taylor swift caption") is False


def test_turn_needs_tool_loop_false_after_arithmetic_extract() -> None:
    assert extract_math_intent("7*8") is not None
    assert turn_needs_tool_loop("7*8", has_verified_math=True, settings=_SETTINGS) is False


@pytest.mark.parametrize(
    "question",
    [
        "y'' of y = x^3 - 3x",
        "f(x) = x^3 - 3x, find f''(x)",
    ],
)
def test_lagrange_primes_are_calculus_not_algebra(question: str) -> None:
    intent, block = _block(question)
    assert intent.kind == "calculus"
    assert intent.operation == "differentiate"
    assert intent.derivative_order == 2
    compact = (block.canonical_answer or "").replace(" ", "").replace("\\", "")
    assert "6x" in compact or "6*x" in compact


def test_y_prime_ode_is_not_stolen_as_derivative() -> None:
    intent = extract_math_intent("y' = 2x")
    assert intent is not None
    assert intent.kind == "calculus"
    assert intent.operation == "dsolve"
    block = math_tools._build_verified_block(intent, _SETTINGS)
    if block is not None:
        compact = (block.canonical_answer or "").replace(" ", "")
        assert "6x" not in compact.replace("\\", "")


def test_dates_and_phones_are_not_verified_arithmetic() -> None:
    for text in ("9/7/2026", "1-800-273-8255"):
        assert math_text_match.bare_arithmetic_expr(text) is None
        assert math_text_match.needs_symbolic(text) is False
        assert extract_math_intent(text) is None
