"""The system prompt is ordered for prompt caching.

The first system message is the same text on every turn of one kind for one user, so a
provider can reuse it; the clock, memory and files of the turn come after it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from app.modules.chat.prompt_constants import (
    FACT_GROUNDING_HINT,
    FORMAT_CONTRACT,
    PHOTO_LOOKUP_HINT,
    STYLE_HINTS,
    UNCLEAR_MESSAGE_HINT,
)
from app.modules.web_search import WEB_SEARCH_HINT
from app.tests.modules.chat.test_prompt_golden import _DEFAULTS, render, resolve

_NINE = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)
_SEVEN_PAST = datetime(2026, 10, 14, 6, 7, tzinfo=UTC)
_QUERY = "what should I cook tonight?"
# A rich turn in a chat with one earlier exchange: memory, schedule and clock all load.
_RICH: dict[str, Any] = {
    "history": [["user", "hi"], ["assistant", "Hey Bini!"], ["user", _QUERY]],
    "kwargs": {"query_text": _QUERY, "rich_context": True, "advice_memory": True, "current": 2},
}


async def _prompt_at(when: datetime, **case: Any) -> list[dict[str, str]]:
    with patch("app.tests.behavior.sweep.SWEEP_NOW", when):
        messages, _out = await render(resolve({**_RICH, **case}, _DEFAULTS))
    return messages


@pytest.mark.asyncio
async def test_the_stable_message_is_byte_identical_at_another_time_with_other_memory() -> None:
    first = await _prompt_at(
        _NINE,
        memory_block="## Preferences\n- Vegetarian.",
        todos_section="Open reminders:\n- Pay rent (due Fri Oct 16)",
    )
    later = await _prompt_at(
        _SEVEN_PAST,
        memory_block="## Preferences\n- Vegetarian.\n- Allergic to peanuts.",
        todos_section="Open reminders:\n- Call the dentist (overdue by 2 days)",
    )
    assert first[0] == later[0]
    # Only the turn's own message differs: its clock, memory and schedule.
    assert first[1] != later[1]
    assert first[2:] == later[2:]
    assert "9:00:00 AM" in first[1]["content"] and "9:07:00 AM" in later[1]["content"]
    for turn_only in ("Current local time", "Digital clock now", "Vegetarian", "Pay rent"):
        assert turn_only not in first[0]["content"]
        assert turn_only in first[1]["content"]


@pytest.mark.asyncio
async def test_fixed_instructions_then_the_users_own_then_the_turns() -> None:
    messages = await _prompt_at(
        _NINE,
        memory_block="## Preferences\n- Vegetarian.",
        todos_section="Open reminders:\n- Pay rent",
        user={"custom_instructions": "Keep it upbeat.", "locale": "es", "job": "Designer"},
        kwargs={**_RICH["kwargs"], "summary": "They planned a trip to Lalibela."},
    )
    stable, turn = messages[0]["content"], messages[1]["content"]
    assert stable.startswith("You are Recall, a helpful personal AI assistant.")
    # The same instructions for every user come before anything about this user.
    users_own = stable.index("User profile")
    for fixed in (
        STYLE_HINTS["balanced"],
        FORMAT_CONTRACT,
        UNCLEAR_MESSAGE_HINT,
        FACT_GROUNDING_HINT,
        WEB_SEARCH_HINT,
        PHOTO_LOOKUP_HINT,
    ):
        assert stable.index(fixed) < users_own
    # Their profile, their own instructions, then their language close the stable message.
    order = ("- Job: Designer", "Keep it upbeat.", "(locale code: es)")
    assert [stable.index(text) for text in order] == sorted(stable.index(t) for t in order)
    assert stable.endswith("do not keep replying in a previous language.")
    # The chat's summary, rewritten every few turns of a long chat, opens the turn's
    # message; the clock, memory and the schedule follow it.
    assert "Lalibela" not in stable
    assert turn.startswith("[BEGIN UNTRUSTED CONTENT — conversation summary]")
    parts = ("Lalibela", "Current local time:", "Digital clock now", "Vegetarian", "Pay rent")
    assert [turn.index(text) for text in parts] == sorted(turn.index(t) for t in parts)
    # The user's latest message stays last.
    assert messages[-1] == {"role": "user", "content": _QUERY}
