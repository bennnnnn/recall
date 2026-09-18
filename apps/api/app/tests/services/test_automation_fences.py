"""Tests for the retired generic ```automation chat protocol."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.automations import fences as automation_fences


def _user() -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    return user


def _settings() -> Settings:
    return Settings(automations_enabled=True)


def _automation() -> MagicMock:
    automation = MagicMock()
    automation.id = uuid4()
    automation.prompt = "Find L3 backend jobs"
    automation.frequency = "daily"
    automation.next_run_at = datetime(2026, 9, 18, 8, tzinfo=UTC)
    return automation


@pytest.mark.asyncio
async def test_no_fence_is_a_noop() -> None:
    text, created = await automation_fences.materialize_automation_fences(
        AsyncMock(),
        user=_user(),
        settings=_settings(),
        assistant_text="Open My Job to configure your search.",
    )
    assert text == "Open My Job to configure your search."
    assert created == 0


@pytest.mark.asyncio
async def test_legacy_create_fence_is_stripped_and_never_materialized() -> None:
    text = (
        "```automation\n"
        '{"prompt":"Find L3 backend jobs","frequency":"daily",'
        '"next_run_at":"2026-09-19T08:00:00-04:00"}\n'
        "```"
    )
    updated, created = await automation_fences.materialize_automation_fences(
        AsyncMock(),
        user=_user(),
        settings=_settings(),
        assistant_text=text,
    )
    assert created == 0
    assert "```automation" not in updated
    assert "Open My Job" in updated


@pytest.mark.asyncio
async def test_retired_fence_keeps_surrounding_prose() -> None:
    text = (
        "I can help with that.\n\n"
        "```automation\n"
        '{"prompt":"Find jobs","frequency":"weekly",'
        '"next_run_at":"2026-09-19T08:00:00Z"}\n'
        "```\n\n"
        "Use the search profile to control the results."
    )
    updated, created = await automation_fences.materialize_automation_fences(
        AsyncMock(),
        user=_user(),
        settings=_settings(),
        assistant_text=text,
    )
    assert created == 0
    assert updated.startswith("I can help with that.")
    assert updated.endswith("Use the search profile to control the results.")
    assert "Open My Job" in updated


@pytest.mark.asyncio
async def test_every_legacy_fence_in_a_reply_is_removed() -> None:
    text = (
        "```automation\n{}\n```\n\n"
        "and\n\n"
        "```automation\n{\"prompt\":\"another\"}\n```"
    )
    updated, created = await automation_fences.materialize_automation_fences(
        AsyncMock(),
        user=_user(),
        settings=_settings(),
        assistant_text=text,
    )
    assert created == 0
    assert "```automation" not in updated
    assert updated.count("Open My Job") == 2


def test_legacy_confirm_fence_remains_readable_for_stored_messages() -> None:
    automation = _automation()
    fence = automation_fences.format_automation_confirm_fence(automation)
    assert fence.strip().startswith("```automation_created")
    assert str(automation.id) in fence
    assert automation.prompt in fence
    assert automation.frequency in fence
