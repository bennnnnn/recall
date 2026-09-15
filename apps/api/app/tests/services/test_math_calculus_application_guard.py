"""A calculus application is not a simultaneous system.

"Area between y=x and y=x^2 from 0 to 1" was claimed by the
simultaneous-equation extractor, which read the two curves as equations to
solve together and answered `x = 0, y = 0; x = 1, y = 1` — where the curves
*cross*. The area is 1/6. Both numbers are real relationships between those
curves; only one of them was asked for, and the verified block tells the model
not to recompute.

Guarding the system extractor alone moved the bug rather than fixing it: the
question then fell through to the single-equation extractor, which answered
`y = 0`. The guard belongs at the funnel every extractor goes through.

None of these are solved here, so the outcome is a refusal — the model answers
unaided, which is the honest result. The same rule the physics kinds use: a
wrong number in a verified block is worse than no block at all.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math.tools import _build_verified_block, extract_math_intent


def _settings() -> Settings:
    return Settings(math_tools_enabled=True)


def _verified_answer(text: str) -> str | None:
    intent = extract_math_intent(text)
    if intent is None:
        return None
    block = _build_verified_block(intent, _settings())
    return None if block is None else block.canonical_answer


REFUSED = [
    # The exact shape that shipped a wrong answer.
    "area between y=x and y=x^2 from 0 to 1",
    "area between the curves y=x and y=x^2 from 0 to 1",
    # The one that leaked to the single-equation extractor when only the
    # system extractor was guarded.
    "find the area between y=sin(x) and y=0 from 0 to pi",
    "area under y=x^2 from 0 to 1",
    "arc length of y=x^2 from 0 to 1",
    "volume of revolution of y=x from 0 to 1 about the x-axis",
    "volume of the solid bounded by y=x and y=0 rotated about the x-axis",
]


@pytest.mark.parametrize("text", REFUSED)
def test_calculus_applications_are_refused_not_answered_sideways(text: str) -> None:
    assert _verified_answer(text) is None


def test_the_area_question_does_not_return_the_intersection_points() -> None:
    """Pinned by value, because the op was right and the question was not.

    `x = 0, y = 0; x = 1, y = 1` is a correct answer to "where do these curves
    meet". It was returned for "what is the area between them".
    """
    answer = _verified_answer("area between y=x and y=x^2 from 0 to 1")
    assert answer is None
    assert answer != "x = 0, y = 0; x = 1, y = 1"


# ---------------------------------------------------------------------------
# The guard is narrow. Everything below must keep answering.
# ---------------------------------------------------------------------------

STILL_ANSWERS = [
    # A genuine simultaneous system, including one whose curves are the same
    # two the area question used.
    ("solve y = x and y = x^2", "x = 0, y = 0; x = 1, y = 1"),
    ("solve 2x + y = 5 and x - y = 1", "x = 2, y = 1"),
    # Geometry areas and volumes name no region between curves.
    ("what is the area of a rectangle 3 by 4", "12"),
    ("what is the area of a circle with radius 5", "78.54"),
    # A definite integral is how this codebase actually does "area under".
    ("integrate x^2 from 0 to 1", "\\frac{1}{3}"),
]


@pytest.mark.parametrize("text,answer", STILL_ANSWERS, ids=[row[0][:40] for row in STILL_ANSWERS])
def test_the_guard_does_not_widen_past_calculus_applications(text: str, answer: str) -> None:
    assert _verified_answer(text) == answer


def test_a_cylinder_volume_is_geometry_not_an_application() -> None:
    """ "volume" alone must not trip the guard — it needs a region word."""
    assert _verified_answer("what is the volume of a cylinder radius 2 height 5") is not None
