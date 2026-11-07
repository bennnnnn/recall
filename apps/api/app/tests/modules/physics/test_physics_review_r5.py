"""The 2026-11-06 review's questions (satellites, spelled numbers, asked ends): each
declines or gets the answer worked by hand.

``review_r5_cases.json`` holds every prompt with its right answer, or null where the
question declines (a spelled quantity, a body with no numbers, an orbiting body's own
mass). Main verified wrong numbers for many of them: 6.9e-8 m/s for a satellite, 0.452 s
for a fall from "ten metres onto a 1 m table".
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.tests.modules.physics.support import answer_number

_SETTINGS = Settings(math_tools_enabled=True)
_CASES: list[dict[str, Any]] = json.loads(
    Path(__file__).with_name("review_r5_cases.json").read_text(encoding="utf-8")
)


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize("case", _CASES, ids=[case["prompt"][:60] for case in _CASES])
def test_a_review_question_declines_or_is_right(case: dict[str, Any]) -> None:
    answer = _answer(case["prompt"])
    if answer is None:
        return
    assert case["answer"] is not None, f"verified a question that declines: {answer}"
    value, _unit = case["answer"]
    assert math.isclose(answer_number(answer), value, rel_tol=0.01), (case["prompt"], answer)
