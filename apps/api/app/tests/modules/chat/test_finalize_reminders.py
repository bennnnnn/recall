"""A reply cut off inside its ```reminder fence reaches the reminder pass without it."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.finalize_reminders import apply_reminder_pass, drop_cut_reminder_fence
from app.modules.chat.turn_prep.context import StreamContext
from app.services.md_fence_scan import close_unclosed_fences
from app.tests.modules.chat.chat_test_support import turn_deps

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


@pytest.mark.asyncio
async def test_a_reply_emptied_by_the_reminder_pass_asks_when() -> None:
    """A reply that was only a fence, with nothing saved, came back empty: done
    carried nothing, so the phone kept the streamed fence."""
    deps = turn_deps(todos={"materialize_reminder_fences": AsyncMock(return_value=("", 0))})
    ctx = SimpleNamespace(
        user=MagicMock(timezone="UTC"),
        user_id=uuid4(),
        chat_id=uuid4(),
        user_timezone="UTC",
        user_message_content="remind me to plate the dinner",
        prompt_messages=[],
        skip_memory_jobs=True,
    )
    text = await apply_reminder_pass(
        deps, AsyncMock(), Settings(), cast(StreamContext, ctx), _CLOSED, None
    )
    assert text == "When should I remind you?"
