"""A function's bare argument ends before the next function name.

SymPy's implicit application carried a bare argument on through the product after it, so
"sin x cos x" was sin(x·cos x): "Differentiate sin x cos x" was a checked
(cos x - x sin x)·cos(x cos x), "Differentiate sin θ cos θ" a checked 0 and "Simplify ln x
sin x" ln(x sin x) (review, 2026-11-14). Each reading here is the bracketed twin's.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.solve.parse import parse_expression
from app.services.subjects.dispatch import build_subject_augmentation


async def _verified(text: str) -> str | None:
    """The turn's checked answer, with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    verified = (await build_subject_augmentation(text, settings)).verified
    return getattr(verified, "canonical_answer", None) if verified is not None else None


@pytest.mark.parametrize(
    ("typed", "bracketed"),
    [
        ("sin x cos x", "sin(x)*cos(x)"),
        ("sin^2 x cos x", "sin(x)**2*cos(x)"),
        ("sin²x cos x", "sin(x)**2*cos(x)"),
        ("sin³x cos²x", "sin(x)**3*cos(x)**2"),
        ("2 sin x cos x", "2*sin(x)*cos(x)"),
        ("sin x tan x", "sin(x)*tan(x)"),
        ("ln x sin x", "ln(x)*sin(x)"),
        ("x sin x cos x", "x*sin(x)*cos(x)"),
        ("sin x cos x tan x", "sin(x)*cos(x)*tan(x)"),
        ("sin x * cos x", "sin(x)*cos(x)"),
        ("sin x·cos x", "sin(x)*cos(x)"),
        ("sin x cos(x)", "sin(x)*cos(x)"),
        ("sin 2x cos x", "sin(2*x)*cos(x)"),
        ("sin 3x cos 2x", "sin(3*x)*cos(2*x)"),
        ("sin xy cos x", "sin(x*y)*cos(x)"),
        ("cos θ sin θ", "cos(θ)*sin(θ)"),
        ("tan θ sec θ", "tan(θ)*sec(θ)"),
        ("sqrt x sin x", "sqrt(x)*sin(x)"),
        ("(sin x cos x)^2", "(sin(x)*cos(x))**2"),
        ("e^sin x cos x", "exp(sin(x))*cos(x)"),
        ("sin x cos x + 1", "sin(x)*cos(x) + 1"),
        # What ended the argument sooner, or brackets it, reads as it did.
        ("e^x sin x", "exp(x)*sin(x)"),
        ("sin x + cos x", "sin(x) + cos(x)"),
        ("sin x/cos x", "sin(x)/cos(x)"),
        ("sin(x cos x)", "sin(x*cos(x))"),
        ("sin cos x", "sin(cos(x))"),
        ("sin x y", "sin(x*y)"),
        ("sin 2x", "sin(2*x)"),
        ("x^cos x", "x**cos(x)"),
    ],
)
def test_a_bare_argument_ends_at_the_next_function(typed: str, bracketed: str) -> None:
    names = ["x", "y", "θ"]
    assert parse_expression(typed, names) == parse_expression(bracketed, names)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Differentiate sin x cos x", r"\cos{\left(2 x \right)}"),
        ("Differentiate sin x * cos x", r"\cos{\left(2 x \right)}"),
        ("Differentiate 2 sin x cos x", r"2 \cos{\left(2 x \right)}"),
        (
            "Differentiate sin²x cos x",
            r"\left(2 - 3 \sin^{2}{\left(x \right)}\right) \sin{\left(x \right)}",
        ),
        (
            "Differentiate ln x sin x",
            r"\ln{\left(x \right)} \cos{\left(x \right)} + \frac{\sin{\left(x \right)}}{x}",
        ),
        (
            "Differentiate x sin x cos x",
            r"x \cos{\left(2 x \right)} + \frac{\sin{\left(2 x \right)}}{2}",
        ),
        ("Differentiate sin θ cos θ", r"\cos{\left(2 θ \right)}"),
        ("Differentiate cos θ sin θ", r"\cos{\left(2 θ \right)}"),
        (
            "Differentiate tan θ sec θ",
            r"\left(2 \tan^{2}{\left(θ \right)} + 1\right) \sec{\left(θ \right)}",
        ),
        ("Integrate sin x cos x", r"\frac{\sin^{2}{\left(x \right)}}{2} + C"),
        ("Integrate 2 sin x cos x", r"\sin^{2}{\left(x \right)} + C"),
        ("Integrate sin²x cos x", r"\frac{\sin^{3}{\left(x \right)}}{3} + C"),
        ("Integrate e^sin x cos x", r"e^{\sin{\left(x \right)}} + C"),
        ("Integrate sin x cos x from 0 to pi/2", r"\frac{1}{2}"),
        ("Simplify sin x cos x", r"\frac{\sin{\left(2 x \right)}}{2}"),
        ("Simplify 2 sin x cos x", r"\sin{\left(2 x \right)}"),
        ("Simplify sin x cos x / cos x", r"\sin{\left(x \right)}"),
        ("Find the derivative of sin x cos x at x = 0", "1"),
        ("Let x = 2. What is sin x cos x?", r"\frac{\sin{\left(4 \right)}}{2}"),
        # Read as before.
        (
            "Differentiate e^x sin x",
            r"\sqrt{2} e^{x} \sin{\left(x + \frac{\pi}{4} \right)}",
        ),
        ("Differentiate sin x + cos x", r"- \sin{\left(x \right)} + \cos{\left(x \right)}"),
        ("Differentiate sin x y", r"y \cos{\left(x y \right)}"),
    ],
)
async def test_a_product_of_functions_is_worked_as_one(question: str, answer: str) -> None:
    assert await _verified(question) == answer
