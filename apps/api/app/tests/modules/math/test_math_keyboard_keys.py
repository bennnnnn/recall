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


@pytest.mark.parametrize(
    ("typed", "plain"),
    [
        (r"$\int x^{2}\,dx$", "integrate x^2 dx"),
        (r"evaluate $\int_{0}^{1}x^{2}\,dx$", "evaluate integrate x^2 from 0 to 1"),
        (r"$\frac{d}{dx}x^{3}$", "d/dx x^3"),
        (r"$\frac{d^{2}}{dx^{2}}x^{3}$", "second derivative of x^3"),
        (r"$\binom{5}{2}$", "C(5,2)"),
        # A number beside a fraction multiplies; a derivative's d/dx does not.
        (r"$44\frac{2}{2}4$", "44* ((2)/(2))* 4"),
        (r"$\frac{1}{2}(4+6)$", "((1)/(2))* (4+6)"),
        (r"$\frac{d}{dx}(x^{2})$", "d/dx (x^2)"),
        (r"$\sin(30^{\circ})$", "sin(30°)"),
        ("no math here", "no math here"),
    ],
)
def test_keyboard_latex_reads_as_plain_notation(typed: str, plain: str) -> None:
    from app.modules.math.tools.keyboard_notation import keyboard_math_to_plain

    assert keyboard_math_to_plain(typed) == plain


@pytest.mark.parametrize(
    ("typed", "answer"),
    [
        (r"$\int x^{2}\,dx$", r"\frac{x^{3}}{3} + C"),
        (r"$\int_{0}^{1}x^{2}\,dx$", r"\frac{1}{3}"),
        (r"$\frac{d}{dx}x^{3}$", r"3 x^{2}"),
        (r"$\frac{d^{2}}{dx^{2}}x^{3}$", r"6 x"),
        (r"$\binom{5}{2}$", "10"),
        # Unread, the model guessed 44 + 2 ÷ 2 + 4 and answered 50.
        (r"$44\frac{2}{2}4$", "176"),
        (r"$\frac{1}{2}+\frac{1}{3}$", r"\frac{5}{6}"),
        (r"$\int_{0}^{1}\frac{1}{2}x\,dx$", r"\frac{1}{4}"),
        (r"$P(5,2)$", "20"),
        (r"solve $2x+1\leq 7$", r"x \le 3"),
        (r"evaluate $\sin(30^{\circ})$", r"\frac{1}{2}"),
        (r"$\sin(\frac{\pi}{6})$", r"\frac{1}{2}"),
        (r"simplify $\mathrm{i}^{2}$", "-1"),
        (r"simplify $(2+3\mathrm{i})(2-3\mathrm{i})$", "13"),
        (r"calculate $|-7|$", "7"),
        (r"calculate $\log(1000)$", "3"),
        # A typed i is still a variable, as an index usually is.
        ("simplify i^2", "i^{2}"),
    ],
)
@pytest.mark.asyncio
async def test_keyboard_notation_is_verified(typed: str, answer: str) -> None:
    assert await _answer(typed) == answer


@pytest.mark.parametrize(
    ("typed", "answer"),
    [
        # Reading only the 2 of π/2 certified 114.59°.
        ("convert pi/2 radians to degrees", r"90\ \mathrm{degrees}"),
        ("convert π/2 rad to degrees", r"90\ \mathrm{degrees}"),
        ("convert 2pi radians to degrees", r"360\ \mathrm{degrees}"),
        (r"convert $\frac{\pi}{2}\mathrm{rad}$ to degrees", r"90\ \mathrm{degrees}"),
        (r"convert $\frac{3\pi}{4}\mathrm{rad}$ to degrees", r"135\ \mathrm{degrees}"),
        ("convert 90 degrees to radians", r"\frac{\pi}{2}\ \mathrm{radians}"),
        (r"convert $45^{\circ}$ to radians", r"\frac{\pi}{4}\ \mathrm{radians}"),
        # Without π the answer stays a decimal.
        ("convert 2 radians to degrees", r"114.591559\ \mathrm{degrees}"),
        ("convert 3/4 km to m", r"750\ \mathrm{m}"),
        ("convert pi/x radians to degrees", None),
    ],
)
@pytest.mark.asyncio
async def test_angle_conversions_read_the_whole_quantity(typed: str, answer: str | None) -> None:
    assert await _answer(typed) == answer
