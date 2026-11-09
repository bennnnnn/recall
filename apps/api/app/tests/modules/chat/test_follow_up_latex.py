"""Follow-up questions read as plain text, with maths left only where it needs typesetting.

Under "A 2 kg block slides down a frictionless 30 degree incline" the chip read "What if θ
was 45^\\textdegree instead?" (2026-11-08): the model copied the reply's LaTeX.
"""

from __future__ import annotations

import pytest

from app.modules.chat.follow_up_latex import plain_follow_up
from app.modules.chat.related_questions import accepted_questions

_INCLINE = "A 2 kg block slides down a frictionless 30 degree incline. Find its acceleration."


@pytest.mark.parametrize(
    ("written", "shown"),
    [
        (r"What if $\theta$ was $45^\text{\textdegree}$ instead?", "What if θ was 45° instead?"),
        (r"What if $\theta = 45^{\circ}$?", "What if θ = 45°?"),
        (r"What if \theta was 60\% larger?", "What if θ was 60% larger?"),
        (r"What if $m = 2\,\mathrm{kg}$?", "What if m = 2 kg?"),
        (r"What if $x \leq 3$?", "What if x ≤ 3?"),
        # What only maths can draw stays as written, for the phone to typeset.
        (r"What if $v_f$ was 30 m/s?", r"What if $v_f$ was 30 m/s?"),
        (r"Why is $\frac{1}{2}$ the answer?", r"Why is $\frac{1}{2}$ the answer?"),
        (r"What if $g$ was $1.6\text{ m/s}^2$?", r"What if $g$ was $1.6\text{ m/s}^2$?"),
        (r"What if $x^2$ was $\pi$?", r"What if $x^2$ was π?"),
        ("What if the incline was 60°?", "What if the incline was 60°?"),
    ],
)
def test_plain_follow_up_writes_each_named_character(written: str, shown: str) -> None:
    assert plain_follow_up(written) == shown


def test_a_follow_up_chip_never_shows_latex_source() -> None:
    kept = accepted_questions(
        _INCLINE,
        [
            r"What if $\theta$ was $45^\text{\textdegree}$ instead?",
            "How far does it slide in 2 s?",
        ],
    )
    assert kept[0] == "What if θ was 45° instead?"
    assert not any("\\" in question for question in kept)
