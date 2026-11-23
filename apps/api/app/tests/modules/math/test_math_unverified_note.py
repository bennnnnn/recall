"""The italic "couldn't verify" line is not part of the reply.

A declined solve used to append it under the answer. A correct square root
or a clock such as 19:00 still got the line. Verified replies already show a
check. The line is removed if it is present and is never added.
"""

from __future__ import annotations

import pytest

from app.modules.math.fence import tidy_and_drop_unverified_math_note

NOTE = "*I couldn't automatically verify this result.*"


@pytest.mark.parametrize(
    "content",
    [
        "A vagina is an internal part of the female reproductive anatomy.",
        "The bakery pickup is at 07:00 and the concert is at 19:00.",
        "The answer is $x = 5$.",
        "So 2+2 = 4 overall.",
        "The mass is 12 kg.",
        "You have 3 options here.",
        "√9 = 3 (the principal square root).",
        "```answer\nx = 2\n```",
        "",
    ],
)
def test_the_note_is_not_added(content: str) -> None:
    assert tidy_and_drop_unverified_math_note(content) == content


@pytest.mark.parametrize(
    "line",
    [
        NOTE,
        "I couldn't automatically verify this result.",
        "I could not verify this result.",
        "Couldn't verify this with SymPy.",
        "This result is not verified.",
        "This answer was not verified.",
    ],
)
def test_a_couldnt_verify_line_is_removed_even_when_the_solve_declined(line: str) -> None:
    stamped = f"The value is 12.\n\n{line}"
    assert tidy_and_drop_unverified_math_note(stamped) == "The value is 12."
    assert "verif" not in tidy_and_drop_unverified_math_note(stamped).lower()
    assert tidy_and_drop_unverified_math_note(line) == ""


def test_the_sentence_is_removed_from_the_same_line_as_the_answer() -> None:
    text = "√9 = 3. I couldn't automatically verify this result."
    assert tidy_and_drop_unverified_math_note(text) == "√9 = 3."


def test_a_stored_clock_note_is_removed() -> None:
    content = f"The bakery pickup is at 07:00 and the concert is at 19:00.\n\n{NOTE}"
    assert tidy_and_drop_unverified_math_note(content) == (
        "The bakery pickup is at 07:00 and the concert is at 19:00."
    )


def test_every_reply_is_tidied_whether_it_had_the_note_or_not() -> None:
    # Kept on purpose (owner, 2026-11-22): straight apostrophes, one blank line, no edges.
    reply = "  It’s 5.\n\n\n\nThat’s all.  "
    assert tidy_and_drop_unverified_math_note(reply) == "It's 5.\n\nThat's all."
