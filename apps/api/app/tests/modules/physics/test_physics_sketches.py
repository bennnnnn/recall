"""The model's own drawing of a physics situation goes where the server draws the picture.

The owner's GCSE set (2026-11-16) got field patterns as rows of slashes and arrows in code
blocks; ``field_sketch_replies.json`` holds those two replies as they came.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.physics.sketches import without_model_drawings

_REPLIES = json.loads((Path(__file__).parent / "field_sketch_replies.json").read_text())["replies"]


@pytest.mark.parametrize("index", range(len(_REPLIES)))
def test_the_owners_ascii_fields_are_taken_out_and_the_words_stay(index: int) -> None:
    reply = _REPLIES[index]["reply"]
    kept = without_model_drawings(reply)
    assert "```" not in kept
    assert "\\" not in kept and "( + )" not in kept
    # The words that explain the pattern stay.
    assert "positive test charge" in kept or "Arrows" in kept
    assert "strongest" in kept.lower() or "greatest strength" in kept.lower()


def test_a_table_of_slashes_is_a_drawing() -> None:
    text = (
        "The pattern:\n\n| \\ | | / |\n|---|---|---|\n| - | + | - |\n| / | | \\ |\n\nLines go out."
    )
    assert without_model_drawings(text) == "The pattern:\n\nLines go out."


def test_a_table_of_words_and_numbers_stays() -> None:
    text = "| Charge | Field |\n|---|---|\n| +2 C | outward |\n| -1 C | inward |"
    assert without_model_drawings(text) == text


@pytest.mark.parametrize(
    "block",
    [
        "```python\nprint('|---|')\nx = '/\\\\'\n```",
        "```\nF = q E\nE = k q / r^2\n```",
    ],
)
def test_code_and_formulas_in_blocks_stay(block: str) -> None:
    text = f"Working:\n\n{block}\n\nDone."
    assert without_model_drawings(text) == text


def test_a_mermaid_diagram_goes_unless_the_user_asked_for_one() -> None:
    text = "Here:\n\n```mermaid\ngraph TD\nA[+] --> B[-]\n```\n\nThat is the field."
    assert "mermaid" not in without_model_drawings(text)
    assert without_model_drawings(text, "make a flowchart of it") == text
