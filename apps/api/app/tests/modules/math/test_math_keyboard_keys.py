"""What the phone's math keyboard types is what the server reads.

The ⁻¹ keys type ``\\cot^{-1}( )``. Read as a power, that was ``1/cot(x)``, and
the derivative of cot⁻¹(x) was certified as 1/cos²(x).
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.solve.parse import _parse_expression
from app.services.subject_solving import build_subject_augmentation


def _settings() -> Settings:
    return Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)


async def _answer(text: str) -> str | None:
    augmentation = await build_subject_augmentation(text, _settings())
    verified = augmentation.verified
    return getattr(verified, "canonical_answer", None) if verified is not None else None


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        (r"\cot^{-1}(x)", "acot(x)"),
        (r"\sec^{-1}(x)", "asec(x)"),
        (r"\csc^{-1}(x)", "acsc(x)"),
        (r"\sinh^{-1}(x)", "asinh(x)"),
        (r"\cosh^{-1}(x)", "acosh(x)"),
        (r"\tanh^{-1}(x)", "atanh(x)"),
        (r"\sin^{-1}x", "asin(x)"),
        ("tan⁻¹(x)", "atan(x)"),
        ("cos^-1(x)", "acos(x)"),
        (r"\arcsin(x)", "asin(x)"),
        (r"\arccos(x)", "acos(x)"),
        (r"\arctan(x)", "atan(x)"),
        (r"\sech(x)", "sech(x)"),
        (r"\csch(x)", "csch(x)"),
        (r"\coth(x)", "coth(x)"),
        # A power after the argument is still a power.
        (r"\sin(x)^{-1}", "1/sin(x)"),
        (r"\sin^{2}(x)", "sin(x)**2"),
    ],
)
def test_parse_reads_keyboard_functions(typed: str, expected: str) -> None:
    assert str(_parse_expression(typed, ["x"])) == expected


@pytest.mark.parametrize(
    ("typed", "answer"),
    [
        (r"differentiate $\cot^{-1}(x)$", r"- \frac{1}{x^{2} + 1}"),
        (r"differentiate $\sinh^{-1}(x)$", r"\frac{1}{\sqrt{x^{2} + 1}}"),
        (r"differentiate $\arcsin(x)$", r"\frac{1}{\sqrt{1 - x^{2}}}"),
        (
            r"differentiate $\sech(x)$",
            r"- \tanh{\left(x \right)} \operatorname{sech}{\left(x \right)}",
        ),
    ],
)
@pytest.mark.asyncio
async def test_inverse_and_hyperbolic_keys_certify_the_right_derivative(
    typed: str, answer: str
) -> None:
    assert await _answer(typed) == answer
