from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.background import billing_reconcile_scheduler
from app.core.config import Settings


class _FakeSessionCM:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_billing_cycle_downgrades_pro_user_without_entitlement():
    pro_id = uuid4()
    session = AsyncMock()
    lock = SimpleNamespace(refresh=AsyncMock(return_value=True))
    settings = Settings(revenuecat_secret_key="sk_test", billing_reconcile_batch_size=25)

    with (
        patch(
            "app.background.billing_reconcile_scheduler.SessionLocal",
            return_value=_FakeSessionCM(session),
        ),
        patch(
            "app.background.billing_reconcile_scheduler.users_repo.list_ids_by_plan",
            AsyncMock(side_effect=[[pro_id], []]),
        ),
        patch(
            "app.background.billing_reconcile_scheduler.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="free"),
        ) as resolve,
        patch(
            "app.background.billing_reconcile_scheduler.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply,
        patch("app.background.billing_reconcile_scheduler.asyncio.sleep", AsyncMock()),
    ):
        await billing_reconcile_scheduler._billing_cycle(settings, lock)

    resolve.assert_awaited_once_with(settings, str(pro_id))
    apply.assert_awaited_once()
    assert apply.await_args.args[1] == str(pro_id)
    assert apply.await_args.kwargs["plan"] == "free"


@pytest.mark.asyncio
async def test_billing_cycle_keeps_pro_when_subscriber_fetch_fails():
    pro_id = uuid4()
    session = AsyncMock()
    lock = SimpleNamespace(refresh=AsyncMock(return_value=True))
    settings = Settings(revenuecat_secret_key="sk_test")

    with (
        patch(
            "app.background.billing_reconcile_scheduler.SessionLocal",
            return_value=_FakeSessionCM(session),
        ),
        patch(
            "app.background.billing_reconcile_scheduler.users_repo.list_ids_by_plan",
            AsyncMock(side_effect=[[pro_id], []]),
        ),
        patch(
            "app.background.billing_reconcile_scheduler.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.background.billing_reconcile_scheduler.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(),
        ) as apply,
        patch("app.background.billing_reconcile_scheduler.asyncio.sleep", AsyncMock()),
    ):
        await billing_reconcile_scheduler._billing_cycle(settings, lock)

    apply.assert_not_awaited()


def test_billing_scheduler_disabled_without_secret():
    settings = Settings(billing_reconcile_enabled=True, revenuecat_secret_key="")
    assert billing_reconcile_scheduler._scheduler_enabled(settings) is False
    settings = Settings(billing_reconcile_enabled=True, revenuecat_secret_key="sk")
    assert billing_reconcile_scheduler._scheduler_enabled(settings) is True
