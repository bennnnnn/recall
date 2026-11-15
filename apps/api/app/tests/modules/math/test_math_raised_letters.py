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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("glued", "spaced"),
    [
        ("Find ∫ x²dx", "Find ∫ x^2 dx"),
        ("∫x^2dx", "∫ x^2 dx"),
        ("∫ 3x²dx", "∫ 3x^2 dx"),
        ("∫ (x+1)dx", "∫ (x+1) dx"),
        ("∫ sin(x)dx", "∫ sin(x) dx"),
        ("Find ∫ x eˣdx", "Find ∫ x e^x dx"),
        ("∫_0^1 x^2dx", "∫_0^1 x^2 dx"),
        ("∫ x²dx from 0 to 2", "∫ x^2 dx from 0 to 2"),
        ("integrate t^2dt", "integrate t^2 dt"),
    ],
)
async def test_a_glued_differential_is_the_differential(glued: str, spaced: str) -> None:
    """``∫ x²dx`` was a checked d·x⁴/4 + C: the glued d was a factor of the integrand."""
    expected = await _verified(spaced)
    assert expected is not None, spaced
    assert await _verified(glued) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("typed", "caret"),
    [
        # One raised run is one exponent on base 10 too: "10²" was read as the literal 100
        # and the ˣ after it as a power of that, so 10²ˣ = 1000 was a checked x = log₂3.
        ("Solve 10²ˣ = 1000", "Solve 10^(2x) = 1000"),
        ("Solve 10³ˣ = 10⁶", "Solve 10^(3x) = 10^6"),
        ("Solve 10²ˣ⁻¹ = 1000", "Solve 10^(2x-1) = 1000"),
        ("Solve 10⁻³ˣ = 1000", "Solve 10^(-3x) = 1000"),
        ("Simplify 10²ˣ · 10ˣ", "Simplify 10^(2x) · 10^x"),
        ("Differentiate 10²ˣ", "Differentiate 10^(2x)"),
        ("Integrate 10³ˣ dx", "Integrate 10^(3x) dx"),
        ("Solve 2 × 10²ˣ = 200", "Solve 2 × 10^(2x) = 200"),
        ("What is 10²⁺¹?", "What is 10^(2+1)?"),
        # Scientific notation is still one number.
        ("Compute 1.8 × 10⁻⁵ × 2", "Compute 1.8 × 10^-5 × 2"),
    ],
)
async def test_a_raised_run_on_ten_is_one_exponent(typed: str, caret: str) -> None:
    expected = await _verified(caret)
    assert expected is not None, caret
    assert await _verified(typed) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("typed", "answer"),
    [
        ("Solve 10²ˣ = 1000", r"x = \frac{3}{2}"),
        ("Solve 10³ˣ = 10⁶", "x = 2"),
        ("Solve 10²ˣ⁻¹ = 1000", "x = 2"),
        ("Solve 10⁻³ˣ = 1000", "x = -1"),
        ("What is 10²⁺¹?", "1000"),
        # A raised index before a root sign is the root's: "2 ³√27" and "2³√27" were
        # 2³·√27, a checked 24√3.
        ("Evaluate 2 ³√27", "6"),
        ("Evaluate 2³√27", "6"),
        ("Evaluate 3 ⁴√16", "6"),
        ("Evaluate 3⁴√16", "6"),
        ("Evaluate 2 ⁵√32", "4"),
        ("Evaluate ³√8", "2"),
        ("Simplify x³√x", r"x \sqrt[3]{x}"),
        # A square root writes no index, so a raised 2 is still its letter's power.
        ("Simplify x²√x", r"x^{2} \sqrt{x}"),
        ("Evaluate 2²√9", "12"),
        # Raised digits on a caret's letter or number go on with its power, as they always
        # did: declined, "Differentiate e^x²" lost its card (2026-11-14).
        ("Differentiate e^x²", r"2 x e^{x^{2}}"),
        ("Find the derivative of e^x²", r"2 x e^{x^{2}}"),
        ("Integrate x·e^x² dx", r"\frac{e^{x^{2}}}{2} + C"),
        ("Differentiate 2^x²", r"2^{x^{2}} x \ln 4"),
        ("Differentiate x^2²", r"4 x^{3}"),
        ("Evaluate 2^3²", "512"),
        # A differential in a Greek letter is the differential: "∫ sin θ dθ" held cos(dθ²).
        ("∫ sin θ dθ", r"- \cos{\left(θ \right)} + C"),
        ("∫ θ^2dθ", r"\frac{θ^{3}}{3} + C"),
        ("∫ cos φ dφ", r"\sin{\left(φ \right)} + C"),
        ("∫ 3 dα", "3 α + C"),
        ("∫ sin(theta) d theta", r"- \cos{\left(\theta \right)} + C"),
        ("integrate sin θ with respect to θ", r"- \cos{\left(θ \right)} + C"),
        ("Differentiate sin θ with respect to θ", r"\cos{\left(θ \right)}"),
        ("Differentiate θ²", "2 θ"),
        # d is still a variable of its own.
        ("Integrate 3d dd", r"\frac{3 d^{2}}{2} + C"),
        ("Solve d² + 3d = 4", r"d = -4 \text{ or } d = 1"),
    ],
)
async def test_a_raised_run_reads_as_written(typed: str, answer: str) -> None:
    assert await _verified(typed) == answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "typed",
    [
        # Straight after a caret's power a raised run is ambiguous: e^((2x)^x) or (e^(2x))^x.
        "Differentiate e^(2x)ˣ",
        "Evaluate 4^(1/2)⁻¹",
        "Evaluate e^2ˣ",
        "Differentiate e^(2x)²",
        "Differentiate e^x⁻¹",
    ],
)
async def test_a_raised_run_after_a_caret_power_is_declined(typed: str) -> None:
    assert await _verified(typed) is None
