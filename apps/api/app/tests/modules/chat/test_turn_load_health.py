"""A new turn reads model health beside its account and routes around failing providers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis
import pytest

from app.core.config import Settings
from app.modules.chat.turn_load import load_new_turn
from app.modules.chat.turn_timing import TurnTimingTracker
from app.services import model_health
from app.services.model_health import HealthSample
from app.tests.modules.chat.chat_test_support import FakeSessionCM, turn_deps


@pytest.mark.asyncio
async def test_unhealthy_aliases_reads_failing_providers_and_never_raises() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    failures = [HealthSample("smart-chat", latency_ms=900, success=False) for _ in range(4)]
    await model_health.record_samples(redis, failures)
    await model_health.record_samples(
        redis, [HealthSample("glm-5.2", latency_ms=900, success=True)]
    )
    settings = Settings()
    found = await model_health.unhealthy_aliases(redis, settings, ["smart-chat", "glm-5.2"])
    assert found == frozenset({"smart-chat"})
    broken = MagicMock()
    with patch.object(model_health, "enrich_models_health", AsyncMock(side_effect=OSError)):
        assert await model_health.unhealthy_aliases(broken, settings, ["smart-chat"]) == frozenset()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["hi", "plan a zero-downtime migration of a postgres schema"])
async def test_load_new_turn_hands_model_health_to_routing(content: str) -> None:
    user = SimpleNamespace(id=uuid4(), plan="pro", enabled_models=None)
    chat = SimpleNamespace(id=uuid4())
    resolve = MagicMock(return_value="glm-5.2")
    deps = turn_deps(
        session_factory=FakeSessionCM,
        quota={
            "has_daily_usage_key": AsyncMock(return_value=True),
            "daily_limit_for_user": lambda _user, _settings: 100_000,
        },
        users={"get_by_id": AsyncMock(return_value=user)},
        chats={"get_by_id": AsyncMock(return_value=chat), "peek_recent_chat": lambda *_a: chat},
        messages={"list_recent": AsyncMock(return_value=[]), "count_for_chat": AsyncMock()},
        plan={"resolve_user_model_override": resolve},
    )
    failing = frozenset({"smart-chat"})
    with (
        patch("app.modules.chat.turn_load.wait_for_pending_finalize", AsyncMock()),
        patch("app.modules.chat.turn_load._classify_turn_mode", AsyncMock()),
        patch.object(model_health, "unhealthy_aliases", AsyncMock(return_value=failing)) as read,
    ):
        turn = await load_new_turn(
            deps,
            AsyncMock(),
            Settings(),
            TurnTimingTracker(),
            user_id=user.id,
            chat_id=chat.id,
            content=content,
            model_alias=None,
            user=None,
            chat=None,
            skip_usage_seed=True,
        )
    read.assert_awaited_once()
    assert resolve.call_args.kwargs["unhealthy"] == failing
    assert turn.unhealthy == failing
    assert turn.model == "glm-5.2"
