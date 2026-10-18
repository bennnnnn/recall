"""A reply cut off inside its ```reminder fence reaches the reminder pass without it."""

from __future__ import annotations

import pytest

from app.modules.chat.finalize_reminders import drop_cut_reminder_fence
from app.services.md_fence_scan import close_unclosed_fences

_CUT = 'Sure.\n\n```reminder\n{"title": "Dentist", "due_at": "2026-10-15T15:00'
_CLOSED = 'Sure.\n\n```reminder\n{"title": "Dentist"}\n```'


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        (_CUT, "Sure."),
        ('```reminder\n{"title": "Den', ""),
        ("Here:\n\n```Reminder\n{", "Here:"),
        (f"```python\nprint(1)\n```\n\n{_CUT}", "```python\nprint(1)\n```\n\nSure."),
        # Closed fences, other open fences and plain prose are not the reminder pass's.
        (_CLOSED, _CLOSED),
        ("Sure.\n\n```python\nprint(1", "Sure.\n\n```python\nprint(1"),
        ('```reminder_proposal\n{"proposal_id": "a"', '```reminder_proposal\n{"proposal_id": "a"'),
        ("No fences at all.", "No fences at all."),
    ],
)
def test_drop_cut_reminder_fence_drops_only_an_open_reminder_fence(text: str, kept: str) -> None:
    assert drop_cut_reminder_fence(text) == kept


def test_a_dropped_fence_leaves_nothing_for_the_fence_repair_to_close() -> None:
    assert close_unclosed_fences(drop_cut_reminder_fence(_CUT)) == "Sure."
