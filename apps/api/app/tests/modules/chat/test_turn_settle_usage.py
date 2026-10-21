"""A settled turn reports the day's usage, which ``done`` carries (code-health audit NET-14)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat import turn_settle
from app.modules.chat.turn_outcome import TurnUsage


def _charge() -> Any:
    return SimpleNamespace(weighted_total=1200, est_cost=0)


@pytest.mark.asyncio
async def test_the_settle_returns_the_days_usage() -> None:
    ctx = SimpleNamespace(user=MagicMock(), user_id=uuid4(), reserved_tokens=1000)
    with (
        patch.object(turn_settle.quota_service, "daily_limit_for_user", return_value=10_000),
        patch.object(turn_settle.quota_service, "adjust_usage", AsyncMock(return_value=8_200)),
    ):
        usage = await turn_settle._settle_quota(AsyncMock(), cast(Any, ctx), Settings(), _charge())
    assert usage == TurnUsage(used_tokens=8_200, daily_limit=10_000)


@pytest.mark.asyncio
async def test_a_failed_settle_reports_no_usage() -> None:
    ctx = SimpleNamespace(user=MagicMock(), user_id=uuid4(), reserved_tokens=1000)
    with (
        patch.object(turn_settle.quota_service, "daily_limit_for_user", return_value=10_000),
        patch.object(
            turn_settle.quota_service, "adjust_usage", AsyncMock(side_effect=OSError("down"))
        ),
        patch.object(turn_settle.quota_service, "mark_usage_needs_heal", AsyncMock()),
        patch.object(turn_settle.asyncio, "sleep", AsyncMock()),
    ):
        usage = await turn_settle._settle_quota(AsyncMock(), cast(Any, ctx), Settings(), _charge())
    assert usage is None
