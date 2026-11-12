"""A worked maths reply's working ends on its value; the card rounds it once.

A card that rounds (≈ 33.51 cm³) has the value unrounded once in the working, an exact
multiple of π rather than the substitution alone, and the working ends on the value it
reaches, as a textbook's does (the "≈" link stays since 2026-11-11).
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.extract import extract_math_intent


def _reply(prompt: str) -> str:
    intent = extract_math_intent(prompt)
    assert intent is not None
    verified = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert verified is not None
    reply = maybe_direct_math_reply(verified, prompt)
    assert reply is not None
    return reply


@pytest.mark.parametrize(
    ("prompt", "exact"),
    [
        ("What is the volume of a sphere with radius 2 cm?", r"\frac{32}{3}\pi"),
        ("Find the volume of a cylinder with radius 3 cm and height 5 cm", r"45\pi"),
        ("Find the area of a circle with radius 3 cm", r"9\pi"),
    ],
)
def test_a_rounded_card_has_its_exact_value_once_in_the_working(prompt: str, exact: str) -> None:
    # The working's chain reaches the exact value, then the rounded one the card shows.
    working = _reply(prompt).split("**Substitution**", 1)[1].split("**Answer**", 1)[0]
    assert f"= {exact}" in working
    last = working.strip().splitlines()[-1]
    assert f"= {exact}" in last and r"\approx" in last
