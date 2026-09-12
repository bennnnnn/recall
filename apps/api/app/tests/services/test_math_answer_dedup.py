"""Equivalent TeX spelling does not create a second canonical-answer card."""

import pytest

from app.services.math_fence import validate_math_fences
from app.services.math_tools import VerifiedMathBlock


@pytest.mark.parametrize(
    "prose,answer",
    [
        (r"The prime factorization is $2^2 \times 3 \times 5$.", r"2^{2} \times 3 \times 5"),
        (r"$60 = 2^2 \times 3 \times 5$", r"2^{2} \times 3 \times 5"),
        (r"$2^{ 2 }\,\times\,3\times5$", r"2^2 \times 3 \times 5"),
        (r"$x^{n}\; +\! y^{2}$", r"x^n + y^2"),
        (r"$x^2\quad+\qquad y^2$", r"x^{2} + y^{2}"),
        (r"$9^{1/6}\,=\,3^{1/3}$", r"9^{1/6} = 3^{1/3}"),
        (r"The volume is $27\,m^3$.", r"27\ \mathrm{m}^{3}"),
        (r"$V = 27\,m^{3}$", r"27\ \mathrm{m}^{3}"),
        (r"$120\;minutes$", r"120\ \mathrm{minutes}"),
        (r"$32\,°F$", r"32\ \mathrm{°F}"),
        (r"\(27\,m^3\)", r"27\ \mathrm{m}^{3}"),
        (r"\[27\,m^3\]", r"27\ \mathrm{m}^{3}"),
        (r"$$27\,m^3$$", r"27\ \mathrm{m}^{3}"),
        (r"\(x=1\)", "x = 1"),
    ],
)
def test_complete_equivalent_math_answer_is_not_appended_again(prose: str, answer: str) -> None:
    verified = VerifiedMathBlock(text="unused", canonical_answer=answer)
    result = validate_math_fences(prose, verified=verified)
    assert "```answer" not in result


@pytest.mark.parametrize(
    "prose,answer",
    [
        (r"$x^12$", r"x^{12}"),
        (r"$x^{12}$", r"x^12"),
        (r"$x^1/6$", r"x^{1/6}"),
        (r"$x^{-1}$", r"x^-1"),
        (r"$x^12$", r"x^{1}"),
        (r"$x^2+1$", r"x^{2}"),
        (r"$12^2$", r"2^{2}"),
        (r"$x^{2+1}$", r"x^{2}+1"),
        (r"$x\quadfoo$", r"xfoo"),
        (r"$\frac{1}{2x}$", r"\frac{1}{2}x"),
        (r"$27\,cm^3$", r"27\ \mathrm{m}^{3}"),
        (r"$27\,m^2$", r"27\ \mathrm{m}^{3}"),
        (r"$27\,M^3$", r"27\ \mathrm{m}^{3}"),
        (r"$1\ \mathrm{MJ}$", r"1\ \mathrm{mJ}"),
        (r"$32\,°C$", r"32\ \mathrm{°F}"),
        (r"\(27\,m^2\)", r"27\ \mathrm{m}^{3}"),
        (r"\(27\,m^3", r"27\ \mathrm{m}^{3}"),
        (r"\$27\,m^3\$", r"27\ \mathrm{m}^{3}"),
    ],
)
def test_different_grouping_or_partial_expression_keeps_canonical_answer(
    prose: str, answer: str
) -> None:
    verified = VerifiedMathBlock(text="unused", canonical_answer=answer)
    result = validate_math_fences(prose, verified=verified)
    assert f"```answer\n{answer}\n```" in result
