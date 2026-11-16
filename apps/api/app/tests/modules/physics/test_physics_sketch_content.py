"""What the sketch rule leaves: real content in plain blocks (review of feat/field-lines).

An ASCII data table, a derivation with arrows and a LaTeX block ending in ``\\\\`` are no
picture of the situation; only a drawing in slashes, bars and arrows is.
"""

from __future__ import annotations

import pytest

from app.modules.physics.sketches import without_model_drawings
from app.services.sketches import is_arrow_sketch


@pytest.mark.parametrize(
    "block",
    [
        "```\n+------+------+\n| t(s) | v    |\n+------+------+\n| 1    | 9.8  |\n+------+------+\n```",
        "```\nF = qE ⇒ E = F/q\nE = 6.0e-9 / 2.0e-12 → 3000 N/C\n```",
        "```\n\\begin{aligned} F &= ma \\\\\na &= F/m \\\\\n\\end{aligned}\n```",
        "```text\nq1 -> q2: 3 N\nq2 -> q1: 3 N\n```",
    ],
)
def test_real_content_in_a_plain_block_stays(block: str) -> None:
    text = f"Working:\n\n{block}\n\nDone."
    assert without_model_drawings(text) == text


@pytest.mark.parametrize(
    "rows",
    [
        ["   \\  |  /", "  -- ( + ) --", "   /  |  \\"],
        ["( + )   ( - )", "->  ^  <-", "<--  +  -->", "->  v  <-"],
        [" + + + + +", "  |   |   |", "  |   |   |", " - - - - -"],
    ],
)
def test_a_drawing_in_slashes_bars_and_arrows_is_a_sketch(rows: list[str]) -> None:
    assert is_arrow_sketch(rows)
