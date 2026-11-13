"""A school reader answers the question it read, all of it, or nothing.

From a textbook run (2026-11-13): "Simplify by combining like terms: -(m + n) + 2(m - 3n)"
was a checked ratio 2:3, its first two numbers taken from anywhere once the line had a
colon and the word "simplify"; and "each interior angle and each exterior angle of a
regular hexagon" was a checked 60° alone.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.extract import extract_math_intent

_SETTINGS = Settings(math_tools_enabled=True)


@pytest.mark.parametrize(
    "text",
    [
        "Simplify by combining like terms: -(m + n) + 2(m - 3n)",
        "Simplify: 2(m - 3n) + 4",
        "Simplify: 3a + 5 - 2a",
        "Simplify the ratio 4x : 6x",
        # A ratio of two measures in different units needs a conversion first.
        "Express the ratio 30 cm : 2 m in simplest form",
    ],
)
def test_letters_and_a_lead_in_colon_are_no_ratio(text: str) -> None:
    intent = extract_math_intent(text)
    assert intent is None or intent.school_op != "ratio"


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("simplify the ratio 12:18", "2:3"),
        ("Simplify 12 : 18", "2:3"),
        ("what is the ratio 6:8 in simplest form", "3:4"),
        ("Simplify the ratio of boys to girls, 12:18", "2:3"),
    ],
)
def test_a_ratio_is_its_two_numbers_around_one_colon(text: str, answer: str) -> None:
    intent = extract_math_intent(text)
    assert intent is not None and intent.school_op == "ratio"
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None and block.canonical_answer == answer


@pytest.mark.parametrize(
    "text",
    [
        "Find the measure of each interior angle and each exterior angle of a regular hexagon",
        "Find the sum of the interior angles of a pentagon and each interior angle of a regular"
        " pentagon",
    ],
)
def test_a_polygon_question_asking_two_angles_is_not_one_card(text: str) -> None:
    assert extract_math_intent(text) is None


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("find each exterior angle of a regular hexagon", r"60^\circ"),
        ("What is the size of each interior angle of a regular octagon?", r"135^\circ"),
        ("find the sum of the interior angles of a hexagon", r"720^\circ"),
    ],
)
def test_a_polygon_question_asking_one_angle_keeps_its_card(text: str, answer: str) -> None:
    intent = extract_math_intent(text)
    assert intent is not None
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None and block.canonical_answer == answer
