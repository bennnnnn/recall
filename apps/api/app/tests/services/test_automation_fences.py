"""Tests for app.services.automations.fences — chat-based ```automation creation."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.automations import fences as automation_fences
from app.services.automations.crud import AutomationsError


def _user(*, plan: str = "pro") -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.plan = plan
    user.timezone = "UTC"
    return user


def _settings() -> Settings:
    return Settings(automations_enabled=True)


def _automation(**overrides: object) -> MagicMock:
    automation = MagicMock()
    automation.id = overrides.get("id", uuid4())
    automation.prompt = overrides.get("prompt", "Find L3 backend jobs")
    automation.frequency = overrides.get("frequency", "daily")
    automation.next_run_at = overrides.get("next_run_at", datetime(2026, 9, 18, 8, tzinfo=UTC))
    return automation


@pytest.mark.asyncio
async def test_no_fence_is_a_noop():
    session = AsyncMock()
    text, created = await automation_fences.materialize_automation_fences(
        session, user=_user(), settings=_settings(), assistant_text="Sure, what should it do?"
    )
    assert text == "Sure, what should it do?"
    assert created == 0


@pytest.mark.asyncio
async def test_valid_fence_creates_and_strips_to_confirm_fence():
    session = AsyncMock()
    automation = _automation()
    text = (
        "```automation\n"
        '{"prompt":"Find L3 backend jobs","frequency":"daily",'
        '"next_run_at":"2026-09-19T08:00:00-04:00"}\n'
        "```"
    )
    with patch.object(
        automation_fences, "create_automation", AsyncMock(return_value=automation)
    ) as create:
        updated, created_count = await automation_fences.materialize_automation_fences(
            session, user=_user(), settings=_settings(), assistant_text=text
        )
    assert created_count == 1
    assert "```automation\n" not in updated
    assert "```automation_created" in updated
    assert str(automation.id) in updated
    assert create.await_args.kwargs["prompt"] == "Find L3 backend jobs"
    assert create.await_args.kwargs["frequency"] == "daily"


@pytest.mark.asyncio
async def test_fence_keeps_surrounding_prose():
    session = AsyncMock()
    automation = _automation()
    text = (
        "Done — every day at 8am I'll check for new postings.\n\n"
        "```automation\n"
        '{"prompt":"Find L3 backend jobs","frequency":"daily",'
        '"next_run_at":"2026-09-19T08:00:00-04:00"}\n'
        "```"
    )
    with patch.object(automation_fences, "create_automation", AsyncMock(return_value=automation)):
        updated, _created = await automation_fences.materialize_automation_fences(
            session, user=_user(), settings=_settings(), assistant_text=text
        )
    assert updated.startswith("Done — every day at 8am I'll check for new postings.")


@pytest.mark.asyncio
async def test_invalid_json_fence_is_replaced_with_explanation():
    session = AsyncMock()
    text = '```automation\n{"prompt":"x"}\n```'  # missing frequency/next_run_at
    with patch.object(automation_fences, "create_automation", AsyncMock()) as create:
        updated, created = await automation_fences.materialize_automation_fences(
            session, user=_user(), settings=_settings(), assistant_text=text
        )
    assert created == 0
    assert "```automation" not in updated
    assert "could not create" in updated.lower()
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_blank_prompt_is_rejected():
    session = AsyncMock()
    text = (
        "```automation\n"
        '{"prompt":"   ","frequency":"daily","next_run_at":"2026-09-19T08:00:00-04:00"}\n'
        "```"
    )
    with patch.object(automation_fences, "create_automation", AsyncMock()) as create:
        _updated, created = await automation_fences.materialize_automation_fences(
            session, user=_user(), settings=_settings(), assistant_text=text
        )
    assert created == 0
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_free_user_gets_the_service_error_instead_of_a_created_chip():
    session = AsyncMock()
    text = (
        "```automation\n"
        '{"prompt":"Find L3 backend jobs","frequency":"daily",'
        '"next_run_at":"2026-09-19T08:00:00-04:00"}\n'
        "```"
    )
    with patch.object(
        automation_fences,
        "create_automation",
        AsyncMock(side_effect=AutomationsError("Automations require Recall Pro", status_code=403)),
    ):
        updated, created = await automation_fences.materialize_automation_fences(
            session, user=_user(plan="free"), settings=_settings(), assistant_text=text
        )
    assert created == 0
    assert "```automation_created" not in updated
    assert "Recall Pro" in updated


@pytest.mark.asyncio
async def test_active_cap_reached_gets_the_service_error():
    session = AsyncMock()
    text = (
        "```automation\n"
        '{"prompt":"Find L3 backend jobs","frequency":"daily",'
        '"next_run_at":"2026-09-19T08:00:00-04:00"}\n'
        "```"
    )
    with patch.object(
        automation_fences,
        "create_automation",
        AsyncMock(
            side_effect=AutomationsError(
                "You can have up to 5 active automations at a time", status_code=422
            )
        ),
    ):
        updated, created = await automation_fences.materialize_automation_fences(
            session, user=_user(), settings=_settings(), assistant_text=text
        )
    assert created == 0
    assert "up to 5 active automations" in updated


def test_confirm_fence_carries_id_prompt_frequency_and_time():
    automation = _automation()
    fence = automation_fences.format_automation_confirm_fence(automation)
    assert fence.strip().startswith("```automation_created")
    assert str(automation.id) in fence
    assert automation.prompt in fence
    assert automation.frequency in fence
