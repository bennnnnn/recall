"""A power typed with raised letters is the power typed with a caret, through the whole turn.

The grade 12 textbook round (2026-11-13) found checked answers to a different question:
"Integrate eˣ cos(2x) with respect to x using integration by parts" got ˣ·e·sin(2x)/2 + C,
"∫ x eˣ dx" got e·x²·ˣ/2 + C and the derivative of 2ˣ was 0, because ˣ reached SymPy as a
symbol of its own. Each prompt here must verify exactly what its caret twin verifies, and
prose with raised letters must stay prose.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.tools.prompt import needs_symbolic_math
from app.services.subjects.dispatch import build_subject_augmentation


async def _verified(text: str) -> str | None:
    """The turn's checked answer, with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    verified = (await build_subject_augmentation(text, settings)).verified
    return getattr(verified, "canonical_answer", None) if verified is not None else None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("typed", "caret"),
    [
        (
            "Integrate eˣ cos(2x) with respect to x using integration by parts.",
            "Integrate e^x cos(2x) with respect to x using integration by parts.",
        ),
        ("Evaluate ∫ eˣ sin 2x dx", "Evaluate ∫ e^x sin 2x dx"),
        ("Find ∫ x eˣ dx", "Find ∫ x e^x dx"),
        ("Evaluate ∫ x² eˣ dx", "Evaluate ∫ x^2 e^x dx"),
        ("Differentiate y = eˣ sin x", "Differentiate y = e^x sin x"),
        ("Find the derivative of 2ˣ", "Find the derivative of 2^x"),
        ("Differentiate e⁻ˣ", "Differentiate e^(-x)"),
        ("Find the derivative of e⁻²ˣ", "Find the derivative of e^(-2x)"),
        ("Integrate e²ˣ dx", "Integrate e^(2x) dx"),
        ("Differentiate 2ˣ⁺¹ with respect to x", "Differentiate 2^(x+1) with respect to x"),
        ("Find d/dx(xⁿ)", "Find d/dx(x^n)"),
        ("Simplify aᵇ · aᶜ", "Simplify a^b · a^c"),
        ("Solve eˣ = 5", "Solve e^x = 5"),
        ("Solve 2ˣ = 32", "Solve 2^x = 32"),
        ("Evaluate ∫₀¹ eˣ dx", "Evaluate ∫_0^1 e^x dx"),
        ("Evaluate ∫₋₁¹ x² dx", "Evaluate ∫_-1^1 x^2 dx"),
        ("Evaluate ∫₁ᵉ ln x dx", "Evaluate ∫_1^e ln x dx"),
        ("Find the limit of (1 + 1/n)ⁿ as n → ∞", "Find the limit of (1 + 1/n)^n as n → ∞"),
        (
            "Differentiate h(x) = 3ˣ × 3ˣ × 2²ˣ with respect to x.",
            "Differentiate h(x) = 3^x × 3^x × 2^(2x) with respect to x.",
        ),
        # Glued to the word after it, the power still ends where it was raised.
        ("Differentiate eˣsin x", "Differentiate e^x sin x"),
        ("Integrate eˣsin(x) dx", "Integrate e^x sin(x) dx"),
    ],
)
async def test_a_raised_power_verifies_what_its_caret_twin_does(typed: str, caret: str) -> None:
    expected = await _verified(caret)
    assert expected is not None, caret
    assert await _verified(typed) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("typed", "answer"),
    [
        ("Evaluate ∫₀¹ eˣ dx", "e - 1"),
        ("Solve eˣ = 5", r"x = \ln 5"),
        ("Find d/dx(xⁿ)", "n x^{n - 1}"),
        ("Find the derivative of 2ˣ", r"2^{x} \ln 2"),
    ],
)
async def test_a_raised_power_gets_the_right_answer(typed: str, answer: str) -> None:
    assert await _verified(typed) == answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "typed",
    [
        # A raised letter after a space raises nothing, and is never a symbol ˣ.
        "Differentiate e ˣ",
        "Integrate x ˣ dx",
        # Before a letter of another alphabet, it is a sound's.
        "Differentiate eⁱᶿ",
    ],
)
async def test_a_raised_letter_no_power_holds_verifies_nothing(typed: str) -> None:
    assert await _verified(typed) is None


@pytest.mark.parametrize(
    "prose",
    [
        "In IPA, aspirated stops are written pʰ, tʰ and kʰ. Why does English aspirate them?",
        "How do you pronounce the word [ˈtʰɑp] in American English?",
        "Tell me about the Kʷak̓ʷala language and where it is spoken.",
        "What happened in the 21ˢᵗ century so far?",
        "The 2ⁿᵈ and 3ʳᵈ place runners finished together.",
        "Le 1ᵉʳ mai est un jour férié en France ?",
        "My friend signs her name as Mˡˡᵉ Dupont, is that French?",
        "Why is the ˣ key on my phone keyboard so small?",
        "Is nʲ a palatalized n in Russian?",
    ],
)
def test_prose_with_raised_letters_is_not_maths(prose: str) -> None:
    assert not needs_symbolic_math(prose)

