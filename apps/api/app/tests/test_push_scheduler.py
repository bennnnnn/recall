"""Push scheduler lock tests and the production two-session cycle."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.background import push_scheduler
from app.core.config import Settings
from app.services.notifications.push import OutboundPush


def test_push_lock_ttl_exceeds_interval():
    assert push_scheduler.LOCK_TTL_SECONDS > push_scheduler.INTERVAL_SECONDS


class _SessionCM:
    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_production_push_cycle_collects_then_finalizes_on_separate_sessions():
    collect_session = object()
    finalize_session = object()
    sessions = iter([collect_session, finalize_session])
    order: list[str] = []
    outbound = [OutboundPush(message={"to": "ExponentPushToken[x]"})]

    async def collect(session: object, redis: object, settings: Settings) -> list[OutboundPush]:
        order.append("collect")
        assert session is collect_session
        return outbound

    async def dispatch(
        items: list[OutboundPush], settings: Settings
    ) -> tuple[list[bool], list[str], list[tuple[str, str]]]:
        order.append("dispatch")
        assert items is outbound
        return [True], [], []

    async def finalize(
        session: object,
        redis: object,
        items: list[OutboundPush],
        delivered: list[bool],
    ) -> None:
        order.append("finalize")
        assert session is finalize_session
        assert delivered == [True]

    with (
        patch(
            "app.background.push_scheduler.SessionLocal",
            side_effect=lambda: _SessionCM(next(sessions)),
        ),
        patch("app.background.push_scheduler.get_redis_client", return_value=AsyncMock()),
        patch(
            "app.background.push_scheduler.push_notifications.collect_push_outbound",
            collect,
        ),
        patch("app.background.push_scheduler.push_notifications.dispatch_expo", dispatch),
        patch(
            "app.background.push_scheduler.push_notifications.finalize_push_deliveries",
            finalize,
        ),
    ):
        await push_scheduler._push_cycle(Settings(push_enabled=True), MagicMock())

    assert order == ["collect", "dispatch", "finalize"]


@pytest.mark.asyncio
async def test_production_push_cycle_skips_dispatch_when_collect_is_empty():
    dispatch = AsyncMock()
    finalize = AsyncMock()
    with (
        patch(
            "app.background.push_scheduler.SessionLocal",
            return_value=_SessionCM(object()),
        ),
        patch("app.background.push_scheduler.get_redis_client", return_value=AsyncMock()),
        patch(
            "app.background.push_scheduler.push_notifications.collect_push_outbound",
            AsyncMock(return_value=[]),
        ),
        patch("app.background.push_scheduler.push_notifications.dispatch_expo", dispatch),
        patch(
            "app.background.push_scheduler.push_notifications.finalize_push_deliveries",
            finalize,
        ),
    ):
        await push_scheduler._push_cycle(Settings(push_enabled=True), MagicMock())

    dispatch.assert_not_awaited()
    finalize.assert_not_awaited()
