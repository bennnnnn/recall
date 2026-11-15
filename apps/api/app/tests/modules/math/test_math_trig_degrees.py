"""A degree mark ends the trig call it closes, in a sum, product, difference or quotient.

"Evaluate sin 30° + cos 60°" was a checked -0.00748 and "sin 30° cos 60°" a checked -0.0087,
on main too: the one-call reader took everything after ``sin`` as its angle and worked
sin((30° + cos 60)·π/180) (review, 2026-11-15). What it cannot split is declined.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.subjects.dispatch import build_subject_augmentation


async def _verified(text: str) -> str | None:
    """The turn's checked answer, with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    verified = (await build_subject_augmentation(text, settings)).verified
    return getattr(verified, "canonical_answer", None) if verified is not None else None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Evaluate sin 30° + cos 60°", "1"),
        ("Evaluate sin 30° cos 60°", r"\frac{1}{4}"),
        ("Evaluate sin 30° × cos 60°", r"\frac{1}{4}"),
        ("Evaluate sin 30° · cos 60°", r"\frac{1}{4}"),
        ("What is sin 30° cos 60°?", r"\frac{1}{4}"),
        ("Evaluate sin 30° - cos 60°", "0"),
        ("Evaluate sin 30° / cos 30°", r"\frac{\sqrt{3}}{3}"),
        ("Evaluate 2 sin 30° cos 30°", r"\frac{\sqrt{3}}{2}"),
        ("Evaluate sin 45° cos 45°", r"\frac{1}{2}"),
        ("Evaluate 3 sin 30°", r"\frac{3}{2}"),
        ("Evaluate sin 30° + 1", r"\frac{3}{2}"),
        ("Evaluate cos 60° + sin 30° + tan 45°", "2"),
        # tan, sec, csc and cot alike, and a power on the name.
        ("Evaluate tan 45° + sin 90°", "2"),
        ("Evaluate sec 60° + 1", "3"),
        ("Evaluate tan 45° sec 60°", "2"),
        ("Evaluate cot 45° + csc 30°", "3"),
        ("Evaluate sin²30°", r"\frac{1}{4}"),
        ("Evaluate sin²30° + cos²30°", "1"),
        ("Evaluate sin^2 30° + cos^2 30°", "1"),
        ("Evaluate sin 30 degrees + cos 60 degrees", "1"),
        # A call in radians beside them, its angle bracketed.
        ("Evaluate sin 30° + cos(π/3)", "1"),
        # Read as before.
        ("Evaluate sin(30°) + cos(60°)", "1"),
        ("Evaluate sin(30°)cos(60°)", r"\frac{1}{4}"),
        ("Evaluate sin 30°", r"\frac{1}{2}"),
        ("Evaluate sin(π/6) + cos(π/3)", "1"),
    ],
)
async def test_each_degree_call_is_its_own_angle(question: str, answer: str) -> None:
    assert await _verified(question) == answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        # A degree mark no call holds: sin(30°) + 15°, or 30° + 15° read twice in degrees
        # (a checked 0.268 for sin 45°).
        "Evaluate sin 30° + 15°",
        "Evaluate sin(30° + 15°)",
        # A bare radian call whose argument nothing ends, an inverse, or another name.
        "Evaluate sin 30° + cos π/3",
        "Evaluate arcsin 0.5 + cos 60°",
        "Evaluate sin⁻¹(0.5) + cos 60°",
        "Evaluate tan⁻¹ 1 + sin 30°",
        "Evaluate sin 30° + cos(1)",
    ],
)
async def test_a_degree_call_beside_what_cannot_be_split_gets_no_card(question: str) -> None:
    assert await _verified(question) is None
