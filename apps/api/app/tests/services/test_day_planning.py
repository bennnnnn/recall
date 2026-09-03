"""Day-planning snapshot: home starters, inject, and connect-note copy."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.calendar import (
    CALENDAR_HINT,
    format_not_connected_calendar_block,
    should_inject_calendar_block,
)
from app.services.chat.prompt_builder import _integration_hints, _style_format_hints
from app.services.chat.prompt_constants import DAY_LEARNING_SNAPSHOT_HINT, DAY_PLANNING_ANSWER_HINT
from app.services.chat.turn_prep.integrations import _inject_integration_blocks
from app.services.day_planning import (
    is_day_planning_question,
    is_day_reflection_question,
    needs_gmail_for_day_planning,
)
from app.services.email import (
    GMAIL_HINT,
    format_not_connected_gmail_block,
    should_inject_gmail_block,
)
from app.services.home.time_starters import time_starters
from app.services.todos.prompt_context import should_inject_todos_prompt

# Every Home time-starter prompt plus the two welcome chips.
# wants_gmail is False on reflection (inbox fetch skipped).
_HOME_STARTERS: list[tuple[str, bool, bool]] = [
    ("Help me plan my day based on what you know about me.", True, True),
    ("What should I focus on today?", True, True),
    ("What am I trying to get done today?", True, True),
    ("What's still open for me to finish today?", True, True),
    ("How did my day go? Help me reflect and wrap up loose ends.", True, False),
    ("What's still open for me to finish tonight?", True, True),
    ("I'm still up — what should I tackle or wind down?", True, False),
    ("I have a quick thought I want to talk through.", False, False),
    ("I want to talk something through — ask me a good opening question.", False, False),
    ("What can you help me with? Give a few concrete examples.", False, False),
]


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "How's my day looking so far — anything you think I should prioritize?",
            True,
        ),
        ("Help me plan my day based on what you know about me.", True),
        ("What should I focus on today?", True),
        ("How did my day go? Help me reflect and wrap up loose ends.", True),
        ("What's still open for me to finish tonight?", True),
        ("What's on my calendar today?", False),
        ("check my email", False),
        ("Tell me a joke", False),
    ],
)
def test_is_day_planning_question(text, expected):
    assert is_day_planning_question(text) is expected


def test_reflection_skips_gmail_but_still_day_planning():
    text = "How did my day go? Help me reflect and wrap up loose ends."
    assert is_day_planning_question(text)
    assert is_day_reflection_question(text)
    assert not needs_gmail_for_day_planning(text)


def test_morning_planning_still_wants_gmail():
    text = "How's my day looking so far — anything you think I should prioritize?"
    assert is_day_planning_question(text)
    assert not is_day_reflection_question(text)
    assert needs_gmail_for_day_planning(text)


@pytest.mark.parametrize("prompt,is_planning,wants_gmail", _HOME_STARTERS)
def test_home_starter_day_planning_and_gmail_flags(prompt, is_planning, wants_gmail):
    assert is_day_planning_question(prompt) is is_planning
    assert needs_gmail_for_day_planning(prompt) is wants_gmail
    assert should_inject_calendar_block(prompt) is is_planning
    assert should_inject_gmail_block(prompt) is wants_gmail
    assert should_inject_todos_prompt([], query_text=prompt) is is_planning


def test_every_time_starter_prompt_is_classified():
    """Hour bands must not grow a starter the snapshot detector misses."""
    user = MagicMock()
    user.name = "Dev"
    covered = {prompt for prompt, _, _ in _HOME_STARTERS}
    for hour in range(24):
        with patch(
            "app.services.home.time_starters.local_hour_for_tz",
            return_value=hour,
        ):
            for starter in time_starters(user, MagicMock()):
                assert starter.prompt in covered, starter.prompt


def test_day_planning_answer_hint_uses_plain_markdown_not_callout_cards():
    assert "Always mention both Calendar and Gmail" not in DAY_PLANNING_ANSWER_HINT
    assert "Skip a product with no block" in DAY_PLANNING_ANSWER_HINT
    assert "Only mention Calendar or Gmail" in DAY_PLANNING_ANSWER_HINT
    assert "ordinary markdown prose" in DAY_PLANNING_ANSWER_HINT
    assert "Never a callout card" in DAY_PLANNING_ANSWER_HINT
    assert "both disconnected blocks are present" in DAY_PLANNING_ANSWER_HINT
    assert "Do not offer a setup walkthrough" in DAY_PLANNING_ANSWER_HINT
    assert "Settings → Google Calendar" in DAY_PLANNING_ANSWER_HINT
    assert "Settings → Gmail" in DAY_PLANNING_ANSWER_HINT
    assert "Google Calendar" in DAY_PLANNING_ANSWER_HINT
    assert "Reminders" in DAY_PLANNING_ANSWER_HINT
    assert "Gmail" in DAY_PLANNING_ANSWER_HINT
    assert "Today's learning progress" in DAY_PLANNING_ANSWER_HINT
    assert "Surface this as `> Warning:" not in DAY_PLANNING_ANSWER_HINT
    assert "Surface this as `> Tip:" not in DAY_PLANNING_ANSWER_HINT


def test_day_plan_style_hints_include_snapshot_and_override_format_contract_callouts():
    parts = _style_format_hints(
        query_text="What's still open for me to finish tonight?",
        style="balanced",
        is_day_plan=True,
        minimal_personal_context=False,
    )
    assert DAY_PLANNING_ANSWER_HINT in parts
    assert DAY_LEARNING_SNAPSHOT_HINT in parts
    joined = "\n".join(parts)
    assert "Callouts: a blockquote starting with Tip:" in joined
    assert "Never a callout card" in joined
    assert "Skip a product with no block" in joined


def test_reflection_style_hints_do_not_require_mentioning_gmail():
    parts = _style_format_hints(
        query_text="How did my day go? Help me reflect and wrap up loose ends.",
        style="balanced",
        is_day_plan=True,
        minimal_personal_context=False,
    )
    joined = "\n".join(parts)
    assert "Always mention both Calendar and Gmail" not in joined
    assert "Skip a product with no block" in joined
    assert "end-of-day reflection" in joined


def test_calendar_and_gmail_hints_ban_callout_cards_for_not_connected():
    assert "ordinary markdown prose" in CALENDAR_HINT
    assert "Tip/Warning/Important callout" in CALENDAR_HINT
    assert "Settings → Google Calendar" in CALENDAR_HINT
    assert "ordinary markdown prose" in GMAIL_HINT
    assert "when a Gmail block is present" in GMAIL_HINT
    assert "Tip/Warning/Important callout" in GMAIL_HINT
    assert "Settings → Gmail" in GMAIL_HINT
    assert "Surface this as `> Warning:" not in CALENDAR_HINT
    assert "Surface this as `> Tip:" not in GMAIL_HINT


def test_not_connected_blocks_are_plain_markdown_instructions():
    calendar = format_not_connected_calendar_block()
    gmail = format_not_connected_gmail_block()
    assert "Google Calendar: not connected" in calendar
    assert "Settings → Google Calendar" in calendar
    assert "ordinary markdown prose" in calendar
    assert "Never a callout card" in calendar
    assert "Gmail: not connected" in gmail
    assert "Settings → Gmail" in gmail
    assert "ordinary markdown prose" in gmail
    assert "Never a callout card" in gmail
    assert "Surface this as `> Warning:" not in calendar
    assert "Surface this as `> Tip:" not in gmail


def test_integration_hints_include_calendar_and_gmail_when_enabled():
    parts = _integration_hints(
        settings=Settings(
            google_calendar_enabled=True,
            gmail_enabled=True,
            web_search_enabled=False,
        ),
        query_text="What's still open for me to finish tonight?",
        local_tz="America/Los_Angeles",
        user_locale="en",
        location_for_context=None,
        prompt_location=None,
        memory_block="",
        attachment_rag_block="",
        todos_section=None,
        is_day_plan=True,
        projects_block="",
        summary=None,
    )
    assert CALENDAR_HINT in parts
    assert GMAIL_HINT in parts


async def _inject(query: str, *, calendar: str | None, gmail: str | None) -> str:
    user = MagicMock()
    user.id = uuid4()
    settings = Settings(gmail_enabled=True, google_calendar_enabled=True)
    with (
        patch(
            "app.services.chat.turn_prep.integrations._load_calendar_prompt_block",
            AsyncMock(return_value=calendar),
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_gmail_prompt_block",
            AsyncMock(return_value=gmail),
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_pending_email_nudge",
            AsyncMock(return_value="- should not appear"),
        ),
    ):
        out = await _inject_integration_blocks(
            [{"role": "system", "content": "base"}],
            query,
            user,
            MagicMock(),
            settings,
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            day_reflection=is_day_reflection_question(query),
            has_calendar_write=False,
            gmail_context=None,
            on_status=None,
        )
    return out[0]["content"]


@pytest.mark.asyncio
async def test_tonight_injects_both_not_connected_blocks():
    content = await _inject(
        "What's still open for me to finish tonight?",
        calendar=format_not_connected_calendar_block(),
        gmail=format_not_connected_gmail_block(),
    )
    assert "Google Calendar: not connected" in content
    assert "Gmail: not connected" in content
    assert "Settings → Google Calendar" in content
    assert "Settings → Gmail" in content
    assert "should not appear" not in content
    assert "Surface this as `> Warning:" not in content
    assert "Surface this as `> Tip:" not in content


@pytest.mark.asyncio
async def test_morning_plan_injects_both_not_connected_blocks():
    content = await _inject(
        "Help me plan my day based on what you know about me.",
        calendar=format_not_connected_calendar_block(),
        gmail=format_not_connected_gmail_block(),
    )
    assert "Google Calendar: not connected" in content
    assert "Gmail: not connected" in content


@pytest.mark.asyncio
async def test_reflection_injects_calendar_not_gmail():
    gmail_loader = AsyncMock(return_value=format_not_connected_gmail_block())
    user = MagicMock()
    user.id = uuid4()
    query = "How did my day go? Help me reflect and wrap up loose ends."
    with (
        patch(
            "app.services.chat.turn_prep.integrations._load_calendar_prompt_block",
            AsyncMock(return_value=format_not_connected_calendar_block()),
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_gmail_prompt_block",
            gmail_loader,
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_pending_email_nudge",
            AsyncMock(return_value=None),
        ),
    ):
        out = await _inject_integration_blocks(
            [{"role": "system", "content": "base"}],
            query,
            user,
            MagicMock(),
            Settings(gmail_enabled=True, google_calendar_enabled=True),
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            day_reflection=True,
            has_calendar_write=False,
            gmail_context=None,
            on_status=None,
        )
    content = out[0]["content"]
    gmail_loader.assert_not_awaited()
    assert "Google Calendar: not connected" in content
    assert "Gmail: not connected" not in content


@pytest.mark.asyncio
async def test_connected_calendar_is_not_labeled_disconnected():
    content = await _inject(
        "What's still open for me to finish tonight?",
        calendar="Google Calendar (next 7 days):\n- Team sync at 10:00",
        gmail=format_not_connected_gmail_block(),
    )
    assert "Team sync at 10:00" in content
    assert "Google Calendar: not connected" not in content
    assert "Gmail: not connected" in content


@pytest.mark.asyncio
async def test_connected_gmail_is_not_labeled_disconnected():
    content = await _inject(
        "What's still open for me to finish tonight?",
        calendar=format_not_connected_calendar_block(),
        gmail="Gmail inbox for me@example.com\nNeeds attention: none",
    )
    assert "me@example.com" in content
    assert "Gmail: not connected" not in content
    assert "Google Calendar: not connected" in content


@pytest.mark.asyncio
async def test_casual_turn_does_not_inject_calendar_or_gmail():
    calendar_loader = AsyncMock(return_value=format_not_connected_calendar_block())
    gmail_loader = AsyncMock(return_value=format_not_connected_gmail_block())
    user = MagicMock()
    user.id = uuid4()
    with (
        patch(
            "app.services.chat.turn_prep.integrations._load_calendar_prompt_block",
            calendar_loader,
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_gmail_prompt_block",
            gmail_loader,
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_pending_email_nudge",
            AsyncMock(return_value=None),
        ),
    ):
        out = await _inject_integration_blocks(
            [{"role": "system", "content": "base"}],
            "Tell me a joke",
            user,
            MagicMock(),
            Settings(gmail_enabled=True, google_calendar_enabled=True),
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            day_reflection=False,
            has_calendar_write=False,
            gmail_context=None,
            on_status=None,
        )
    calendar_loader.assert_not_awaited()
    gmail_loader.assert_not_awaited()
    assert out[0]["content"] == "base"
