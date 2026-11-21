"""A picture under its own part: right after that part is answered (owner, 2026-11-21)."""

from __future__ import annotations

import pytest

from app.services.part_place import part_key, place_after_part

_PIC = '```graph\n{"type":"plot"}\n```'

_LAID_OUT = (
    "**Required**\n(a) $h$ (height)\n(b) $A$ (area)\n\n**Solution**\n\n"
    "**(a) Height**\n\n$h = 3$\n\n**Answer (a)**\n\n```answer\nverified: false\nh = 3\n```\n\n"
    "---\n\n**(b) Area**\n\n$A = 48$\n\n**Answer (b)**\n\n```answer\nverified: false\nA = 48\n```\n\n"
    "The height is 3 cm and the area 48 cm²."
)


@pytest.mark.parametrize(
    ("value", "key"),
    [("b", "b"), ("(b)", "b"), ("B", "b"), ("Part c", "c"), ("2", "2"), (2, "2"), ("b)", "b")],
)
def test_part_key_reads_a_part_as_a_reply_writes_it(value: object, key: str) -> None:
    assert part_key(value) == key


@pytest.mark.parametrize("value", [None, "", "z", "part", "ab", True, 9, {"part": "a"}])
def test_part_key_refuses_what_names_no_part(value: object) -> None:
    assert part_key(value) is None


def test_a_picture_goes_right_after_its_part_s_answer_card() -> None:
    out = place_after_part(_LAID_OUT, "a", _PIC)
    assert out is not None
    card_a = out.index("h = 3\n```")
    assert card_a < out.index(_PIC) < out.index("---") < out.index("**(b) Area**")
    out = place_after_part(_LAID_OUT, "b", _PIC)
    assert out is not None
    assert out.index("A = 48\n```") < out.index(_PIC) < out.index("The height is 3 cm")


def test_never_in_the_required_list() -> None:
    """A plain "(b) …" line is the Required list's: part (b) is where it is worked."""
    out = place_after_part(_LAID_OUT, "b", _PIC)
    assert out is not None and out.index(_PIC) > out.index("**Answer (b)**")


def test_a_part_with_no_card_ends_at_the_next_part() -> None:
    text = (
        "**(a) Roots**\n\nThe roots are 1 and 3.\n\n"
        "**(b) Intercept**\n\nIt crosses the y-axis at (0, 1)."
    )
    out = place_after_part(text, "a", _PIC)
    assert out is not None
    assert out.index("1 and 3.") < out.index(_PIC) < out.index("**(b) Intercept**")
    out = place_after_part(text, "b", _PIC)
    assert out is not None and out.rstrip().endswith("```")


def test_a_heading_inside_a_fence_is_no_part() -> None:
    text = "```text\n**Answer (a)**\n```\n\nNo parts here."
    assert place_after_part(text, "a", _PIC) is None


def test_a_part_the_reply_does_not_have_places_nothing() -> None:
    assert place_after_part(_LAID_OUT, "c", _PIC) is None
    assert place_after_part("One answer, no parts.", "a", _PIC) is None
