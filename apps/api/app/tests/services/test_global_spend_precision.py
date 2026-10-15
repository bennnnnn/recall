"""The global spend kill-switch sees cheap turns.

The counter stored ``round(usd * 1000)`` (tenths of a cent). A free-chat
turn costs about $0.0002-0.0005 (DeepSeek Chat at $0.14/$0.28 per M), so most
recorded 0: 10,000 turns at $0.0004 (really $4.00) left the counter at $0.00,
and the cap never tripped on free-tier traffic.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.services import quota as quota_service


@pytest.mark.parametrize(
    "turn_cost_usd, turns, cap_usd, exceeded",
    [
        # $1.00 of cheap turns against a $0.90 cap.
        (0.0004, 2_500, 0.90, True),
        (0.0004, 2_500, 1.10, False),
        # Nine $0.0003 greetings ($0.0027) pass a $0.002 cap; each used to round to 0.
        (0.0003, 9, 0.002, True),
        # Larger fixed costs still add up exactly.
        (0.03, 40, 1.19, True),
        (0.03, 40, 1.21, False),
    ],
)
async def test_global_spend_counts_sub_cent_turns(
    fake_redis: Any, turn_cost_usd: float, turns: int, cap_usd: float, exceeded: bool
) -> None:
    for _ in range(turns):
        await quota_service.record_global_spend(fake_redis, turn_cost_usd)
    settings = Settings(daily_global_spend_usd=cap_usd)
    assert await quota_service.global_spend_exceeded(fake_redis, settings) is exceeded


@pytest.mark.parametrize(
    "legacy_units, cap_usd, exceeded",
    [
        # Spend recorded before the deploy (tenths of a cent) still counts.
        (2_000, 1.50, True),
        (2_000, 2.50, False),
    ],
)
async def test_global_spend_reads_the_pre_deploy_counter(
    fake_redis: Any, legacy_units: int, cap_usd: float, exceeded: bool
) -> None:
    today = quota_service.utc_today().isoformat()
    await fake_redis.set(f"spend_mcents:{today}", legacy_units)
    settings = Settings(daily_global_spend_usd=cap_usd)
    assert await quota_service.global_spend_exceeded(fake_redis, settings) is exceeded
