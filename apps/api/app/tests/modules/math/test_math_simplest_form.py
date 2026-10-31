"""A "simplify" card in the book's form: real odd roots, lowest terms, collected
polynomials, the excluded values that are real, and complex numbers as a + bi."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.modules.math import school as math_school
from app.modules.math.schemas import MathIntent
from app.modules.math.solve.expressions import simplify_expression
from app.modules.math.solve.key_steps import written_side
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.extract import extract_math_intent
from app.modules.math.tools.llm_extract import (
    LLMMathExtract,
    complex_reading,
    llm_extract_math_intent,
)

_SETTINGS = Settings(math_tools_enabled=True)


@pytest.mark.parametrize(
    ("expression", "simplest"),
    [
        # An odd root of a real number is the real root, and radicals combine.
        ("cbrt(162x^5)/cbrt(3x^2)", r"3 \sqrt[3]{2} x"),
        ("cbrt(16x^4)/cbrt(2x)", "2 x"),
        ("cbrt(x^3)", "x"),
        ("cbrt(-8)", "-2"),
        ("cbrt(-8x^6)", "- 2 x^{2}"),
        ("cbrt(-27x^5)", r"- 3 x \sqrt[3]{x^{2}}"),
        ("cbrt(x^2)", r"\sqrt[3]{x^{2}}"),
        # An even root's own domain (x ≥ 0) lets it combine; one radical per index.
        ("sqrt(12x^3)", r"2 x \sqrt{3 x}"),
        ("sqrt(x^5)", r"x^{2} \sqrt{x}"),
        # A rational expression is in lowest terms.
        ("x/(x^3 - 1) / (2 - 1/(1 + 1/(x - 2)))", r"\frac{1}{x^{2} + x + 1}"),
        ("(x^3 - 8)/(x - 2)", "x^{2} + 2 x + 4"),
        # A polynomial is its collected terms when factoring is no shorter.
        ("x^3 + x^2", "x^{3} + x^{2}"),
        ("3x + 2x^2 - x + 4", "2 x^{2} + 2 x + 4"),
    ],
)
def test_simplify_prints_the_book_form(expression: str, simplest: str) -> None:
    assert simplify_expression(expression, "x").latex == simplest


@pytest.mark.parametrize(
    ("expression", "unchanged"),
    [
        # A square root of a square stays |x|: x may be negative.
        ("sqrt(x^2)", r"\left|{x}\right|"),
        ("sqrt(18x^2)", r"3 \sqrt{2} \left|{x}\right|"),
        ("sqrt(50)", r"5 \sqrt{2}"),
        ("sqrt(2)/2", r"\frac{\sqrt{2}}{2}"),
        ("cbrt(54)", r"3 \sqrt[3]{2}"),
        ("x^(1/2)/x^(1/4)", r"\sqrt[4]{x}"),
        # Combining fractions is longer, and it is the answer.
        ("1/x + 1/(x+1)", r"\frac{2 x + 1}{x \left(x + 1\right)}"),
        ("(x^2+5x+6)/(x^2-9)", r"\frac{x + 2}{x - 3}"),
        ("(x+1)^10", r"\left(x + 1\right)^{10}"),
        ("(x+1)^2 - (x-1)^2", "4 x"),
        ("sin(x)^2 + cos(x)^2", "1"),
        ("x + x", "2 x"),
    ],
)
def test_simplify_keeps_forms_already_in_the_book(expression: str, unchanged: str) -> None:
    assert simplify_expression(expression, "x").latex == unchanged


def test_simplified_card_lists_only_real_excluded_values_in_order() -> None:
    intent = MathIntent(
        kind="calculus",
        expr="x/(x^3 - 1) / (2 - 1/(1 + 1/(x - 2)))",
        operation="simplify",
        variable="x",
    )
    block = _build_verified_block(intent, _SETTINGS)

    assert block is not None and block.canonical_answer == r"\frac{1}{x^{2} + x + 1}"
    reply = block.direct_reply or ""
    assert r"x \ne 0,\; x \ne 1,\; x \ne 2" in reply
    assert "i}" not in reply and r"\sqrt{3}" not in reply
    # The typed 1/(x - 2) is a fraction, not the mixed number "1 1/(x - 2)".
    assert r"1 \frac" not in reply


@pytest.mark.parametrize(
    ("typed", "shown"),
    [
        ("1/(x-2)", r"\frac{1}{x - 2}"),
        ("2 - 1/(1 + 1/(x - 2))", r"2 - \frac{1}{1 + \frac{1}{x - 2}}"),
        ("1/x + 1/y", r"\frac{1}{x} + \frac{1}{y}"),
        ("2/(x+1)", r"\frac{2}{x + 1}"),
        ("3(x-2)+4", r"3 \left(x - 2\right) + 4"),
        ("1/2 + x", r"\frac{1}{2} + x"),
    ],
)
def test_written_side_shows_a_unit_fraction_as_typed(typed: str, shown: str) -> None:
    written = written_side(typed, ["x", "y"])
    assert written is not None and written[1] == shown


@pytest.mark.parametrize(
    ("expression", "standard"),
    [
        ("i^320 - 5i^121 + 3i^45", "1 - 2 i"),
        ("(2+3i)/(1-i)", r"- \frac{1}{2} + \frac{5}{2} i"),
        ("1/(2+i)", r"\frac{2}{5} - \frac{1}{5} i"),
        ("(3+2i)(1-i)", "5 - i"),
        ("3+4i", "3 + 4 i"),
        ("(1+i)^2", "2 i"),
        ("i^2", "-1"),
        # 3·sin(30) is negative; it is not split into a sign and a size.
        ("2+3i*sin(30)", r"2 + 3 i \sin{\left(30 \right)}"),
    ],
)
def test_complex_value_prints_as_a_plus_bi(expression: str, standard: str) -> None:
    assert math_school.evaluate_complex(expression) == standard


@pytest.mark.parametrize(
    ("query", "answer"),
    [
        ("Simplify and write in the form a + bi: i^320 - 5i^121 + 3i^45", "1 - 2 i"),
        ("Write in the form a + bi: i^320 - 5i^121 + 3i^45", "1 - 2 i"),
        ("Express (2+3i)/(1-i) in the form a+bi", r"- \frac{1}{2} + \frac{5}{2} i"),
        ("Write (3+2i)(1-i) in standard form a+bi", "5 - i"),
        ("Simplify i^320 - 5i^121 + 3i^45", "1 - 2 i"),
    ],
)
def test_form_a_plus_bi_names_the_answer_not_the_expression(query: str, answer: str) -> None:
    intent = extract_math_intent(query)
    assert intent is not None and intent.kind == "complex"
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None and block.canonical_answer == answer
    reply = maybe_direct_math_reply(block, query)
    assert reply is not None and answer in reply


def test_a_plus_b_form_of_a_line_is_not_complex() -> None:
    assert extract_math_intent("Write 3x + 2 in the form ax + b") is None


@pytest.mark.parametrize(
    ("text", "expression"),
    [
        (
            "Simplify and write in the form a + bi: i^320 - 5i^121 + 3i^45",
            "i^320 - 5*i^121 + 3*i^45",
        ),
        ("Simplify the complex number (2+i)(3-i)", "(2+i)*(3-i)"),
        ("Simplify the imaginary expression 3i + 2i", "3*i + 2*i"),
        ("Simplify i^7 + i^2", "i^7 + i^2"),
    ],
)
def test_llm_simplification_about_complex_numbers_is_complex_arithmetic(
    text: str, expression: str
) -> None:
    intent = MathIntent(kind="calculus", expr=expression, operation="simplify", variable="i")
    read = complex_reading(intent, text)
    assert read is not None and read.kind == "complex" and read.expr == expression


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        # A complex fraction is a fraction of fractions.
        (
            "Simplify the complex fraction (1/x + 1/y)/(1/x - 1/y)",
            MathIntent(kind="calculus", expr="(1/x + 1/y)/(1/x - 1/y)", operation="simplify"),
        ),
        # No i to read.
        (
            "Simplify the complex expression x^2 + 2x",
            MathIntent(kind="calculus", expr="x^2 + 2*x", operation="simplify"),
        ),
        # A letter i with nothing complex about the question.
        (
            "Simplify 3i + 2i",
            MathIntent(kind="calculus", expr="3*i + 2*i", operation="simplify", variable="i"),
        ),
        # Another operation keeps its own reading.
        (
            "Differentiate i^2 x in the form a + bi",
            MathIntent(kind="calculus", expr="i^2*x", operation="differentiate"),
        ),
    ],
)
def test_llm_reading_without_complex_numbers_is_kept(text: str, intent: MathIntent) -> None:
    assert complex_reading(intent, text) is intent


@pytest.mark.asyncio
async def test_llm_extract_reads_i_as_the_imaginary_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake(**kwargs: object) -> LLMMathExtract:
        return LLMMathExtract(
            found=True,
            kind="calculus",
            operation="simplify",
            expr="i^320 - 5*i^121 + 3*i^45",
            variable="i",
        )

    monkeypatch.setattr(litellm_gateway, "complete_structured", fake)
    intent = await llm_extract_math_intent(
        "Simplify and write in the form a + bi: i^320 - 5i^121 + 3i^45",
        Settings(math_tools_enabled=True, math_llm_extract_enabled=True),
    )
    assert intent is not None and intent.kind == "complex"
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None and block.canonical_answer == "1 - 2 i"
