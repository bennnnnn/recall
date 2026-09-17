"""Pydantic validation tests for app.models.schemas.automations."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.schemas.automations import AutomationCreate, AutomationUpdate


def test_automation_create_requires_prompt():
    with pytest.raises(ValidationError):
        AutomationCreate(prompt="   ", frequency="daily", next_run_at=datetime.now(UTC))


def test_automation_create_rejects_unknown_frequency():
    with pytest.raises(ValidationError):
        AutomationCreate(prompt="Find jobs", frequency="hourly", next_run_at=datetime.now(UTC))


def test_automation_create_strips_prompt():
    body = AutomationCreate(
        prompt="  Find L3 jobs  ", frequency="once", next_run_at=datetime.now(UTC)
    )
    assert body.prompt == "Find L3 jobs"


def test_automation_update_rejects_cleared_next_run_at():
    with pytest.raises(ValidationError):
        AutomationUpdate(next_run_at=None)


def test_automation_update_rejects_completed_status():
    with pytest.raises(ValidationError):
        AutomationUpdate(status="completed")


def test_automation_update_allows_partial_patch():
    body = AutomationUpdate(status="paused")
    assert body.model_dump(exclude_unset=True) == {"status": "paused"}
