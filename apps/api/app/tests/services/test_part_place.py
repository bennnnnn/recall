"""A picture under its own part: right after that part is answered (owner, 2026-11-21)."""

from __future__ import annotations

import pytest

from app.services.part.place import part_key, pictures_follow_parts, place_after_part

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


_TWO_PROBLEMS = {
    "a": "Draw the free-body diagram of a 5 kg block on a frictionless 30° incline and find its acceleration.",
    "b": "Draw the circuit for a 12 V battery connected to 4 Ω and 6 Ω resistors in series and find the current.",
}
_INCLINE = '```simulation\n{"type":"incline","mass":5,"angle_deg":30,"path":[[0,0],[1,1],[2,2],[3,3],[4,4]]}\n```'
_CIRCUIT = '```simulation\n{"type":"circuit","emf":12,"resistors":[4,6]}\n```'


def _two_part_reply(*pictures: str) -> str:
    return (
        "📐 **Part a: Incline Physics**\n\n$a = 4.9\\,\\mathrm{m/s^2}$\n\n***\n\n"
        "⚡ **Part b: Series Circuit**\n\n$I = 1.2\\,\\mathrm{A}$\n\n" + "\n\n".join(pictures)
    )


def test_a_picture_one_part_holds_the_values_of_goes_after_that_part() -> None:
    """Live (2026-11-21): the incline of part a sat under part b's circuit."""
    out = pictures_follow_parts(_two_part_reply(_INCLINE, _CIRCUIT), _TWO_PROBLEMS)
    assert out.index("4.9") < out.index('"incline"') < out.index("Part b: Series")
    assert out.index("1.2") < out.index('"circuit"')


def test_a_picture_every_part_shares_or_none_holds_stays() -> None:
    shared = '```graph\n{"type":"plot","label":"launch at 25 m/s"}\n```'
    parts = {"a": "Find its time of flight at 25 m/s.", "b": "Find its range at 25 m/s."}
    reply = "**(a) Time**\n\n$t = 3.3$\n\n**(b) Range**\n\n$R = 63$\n\n" + shared
    assert pictures_follow_parts(reply, parts) == reply
    assert pictures_follow_parts(
        _two_part_reply(_CIRCUIT), {"a": "x", "b": "y"}
    ) == _two_part_reply(_CIRCUIT)


def test_a_question_without_parts_is_left_alone() -> None:
    reply = _two_part_reply(_INCLINE)
    assert pictures_follow_parts(reply, {}) == reply


def test_two_pictures_at_the_end_each_go_to_their_own_part() -> None:
    """Review (#2521): moving one picture shifted the other's offsets, so it stayed put."""
    parts = {
        "a": "Sketch y = x^2 - 9 and find its roots.",
        "b": "Sketch y = 5x + 7 and its intercept.",
    }
    graph_a = '```graph\n{"type":"plot","label":"y = x^2 - 9"}\n```'
    graph_b = '```graph\n{"type":"plot","label":"y = 5x + 7"}\n```'
    reply = (
        "**(a) Roots**\n\n$x = \\pm 3$\n\n**(b) Intercept**\n\n$y = 7$\n\nBoth done.\n\n"
        f"{graph_a}\n\n{graph_b}"
    )
    out = pictures_follow_parts(reply, parts)
    assert out.index("x = \\pm 3") < out.index("x^2 - 9") < out.index("**(b) Intercept**")
    # (b)'s picture is inside (b)'s own section already (it runs to the reply's end).
    assert out.index("**(b) Intercept**") < out.index("5x + 7")
