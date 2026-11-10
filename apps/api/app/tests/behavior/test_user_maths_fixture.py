"""A sent message's maths is drawn as the server reads it.

The phone draws maths a user types as plain text in the sent bubble
(``apps/mobile/lib/math/normalizeImplicit.ts``); ``docs/fixtures/user_maths_cases.json``
holds each message, the markdown its bubble draws and ``typed``, the words of the message
that hold the maths. The phone's test (``lib/math/__tests__/userMathsFixture.test.ts``) holds
the bubble to ``drawn``. Here the maths in ``drawn``, read through the LaTeX path a keypad
message takes, and ``typed``, read as a turn reads a message, must be one expression: a
bracket the bubble dropped ("ln(x^2 + 1)" drawn as "ln x² + 1") changes what is solved.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from sympy import simplify

from app.modules.math.solve.latex_normalize import normalize_latex_to_sympy
from app.modules.math.solve.parse import parse_expression

FIXTURE = Path(__file__).resolve().parents[5] / "docs" / "fixtures" / "user_maths_cases.json"
_MATH_SPAN = re.compile(r"\$([^$]+)\$")


def _cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    return cases


def _sides(text: str) -> list[Any]:
    """Each side of an equation (or the one expression), parsed."""
    return [parse_expression(side) for side in text.split("=")]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["id"])
def test_the_bubble_draws_what_the_server_reads(case: dict[str, Any]) -> None:
    assert case["typed"] in case["text"]
    spans = _MATH_SPAN.findall(case["drawn"])
    assert len(spans) == 1, f"{case['id']}: one formula drawn, got {spans}"
    drawn = _sides(normalize_latex_to_sympy(f"${spans[0]}$"))
    typed = _sides(normalize_latex_to_sympy(case["typed"]))
    assert len(drawn) == len(typed)
    for drawn_side, typed_side in zip(drawn, typed, strict=True):
        assert simplify(drawn_side - typed_side) == 0, (
            f"{case['id']}: the bubble draws {spans[0]!r}, the server reads {case['typed']!r}"
        )
