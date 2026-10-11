"""The unverified sentence is not part of the reply.

A declined solve used to append "*I couldn't automatically verify this result.*"
whenever the text contained a digit. A clock answer (07:00, 19:00) qualified.
The sentence stays out of the reply, including a stored copy that already has it.
"""

from __future__ import annotations

import pytest

from app.modules.math.fence import append_unverified_math_note

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
        "```answer\nx = 2\n```",
    ],
)
def test_note_is_not_added_to_a_reply(content: str) -> None:
    assert append_unverified_math_note(content) == content


def test_a_stored_note_is_removed() -> None:
    content = f"The bakery pickup is at 07:00 and the concert is at 19:00.\n\n{NOTE}"
    assert append_unverified_math_note(content) == (
        "The bakery pickup is at 07:00 and the concert is at 19:00."
    )
    assert NOTE not in append_unverified_math_note(NOTE)
