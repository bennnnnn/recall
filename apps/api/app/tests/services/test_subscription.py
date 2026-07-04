from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways import revenuecat_gateway
from app.services import subscription as subscription_service


def test_entitlement_active_lifetime():
    payload = {
        "subscriber": {
            "entitlements": {
                "pro": {"expires_date": None},
            }
        }
    }
    assert revenuecat_gateway.entitlement_active(payload, "pro") is True


def test_entitlement_active_future_expiry():
    future = (datetime.now(UTC) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    payload = {"subscriber": {"entitlements": {"pro": {"expires_date": future}}}}
    assert revenuecat_gateway.entitlement_active(payload, "pro") is True


def test_entitlement_active_expired():
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    payload = {"subscriber": {"entitlements": {"pro": {"expires_date": past}}}}
    assert revenuecat_gateway.entitlement_active(payload, "pro") is False


@pytest.mark.asyncio
async def test_sync_user_plan_from_revenuecat_upgrades():
    user = MagicMock()
    user.id = uuid4()
    user.plan = "free"
    session = AsyncMock()
    settings = Settings(revenuecat_secret_key="sk_test", revenuecat_entitlement_id="pro")
    payload = {"subscriber": {"entitlements": {"pro": {"expires_date": None}}}}

    with patch(
        "app.services.subscription.revenuecat_gateway.fetch_subscriber",
        AsyncMock(return_value=payload),
    ):
        with patch(
            "app.services.subscription.users_repo.update",
            AsyncMock(return_value=MagicMock(plan="pro")),
        ) as update:
            updated = await subscription_service.sync_user_plan_from_revenuecat(
                session, user, settings
            )
    assert updated.plan == "pro"
    update.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_plan_for_app_user_id():
    user_id = uuid4()
    user = MagicMock()
    user.plan = "free"
    session = AsyncMock()

    with patch(
        "app.services.subscription.users_repo.get_by_id",
        AsyncMock(return_value=user),
    ):
        with patch(
            "app.services.subscription.users_repo.update",
            AsyncMock(return_value=MagicMock(plan="pro")),
        ) as update:
            ok = await subscription_service.apply_plan_for_app_user_id(
                session,
                str(user_id),
                plan="pro",
            )
    assert ok is True
    update.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_revenuecat_transfer_downgrades_old_and_syncs_new():
    old_id = uuid4()
    new_id = uuid4()
    user = MagicMock()
    user.id = new_id
    user.plan = "free"
    session = AsyncMock()
    settings = Settings(revenuecat_secret_key="sk_test", revenuecat_entitlement_id="pro")

    with patch(
        "app.services.subscription.apply_plan_for_app_user_id",
        AsyncMock(return_value=True),
    ) as apply_mock:
        with patch(
            "app.services.subscription.users_repo.get_by_id",
            AsyncMock(return_value=user),
        ):
            with patch(
                "app.services.subscription.sync_user_plan_from_revenuecat",
                AsyncMock(return_value=MagicMock(plan="pro")),
            ) as sync_mock:
                await subscription_service.handle_revenuecat_transfer(
                    session,
                    settings,
                    new_app_user_id=str(new_id),
                    transferred_from=[str(old_id), "  "],
                )

    apply_mock.assert_awaited_once_with(session, str(old_id), plan="free")
    sync_mock.assert_awaited_once_with(session, user, settings)


@pytest.mark.asyncio
async def test_handle_revenuecat_transfer_skips_invalid_new_id():
    session = AsyncMock()
    settings = Settings()

    with patch(
        "app.services.subscription.apply_plan_for_app_user_id",
        AsyncMock(),
    ) as apply_mock:
        with patch(
            "app.services.subscription.sync_user_plan_from_revenuecat",
            AsyncMock(),
        ) as sync_mock:
            await subscription_service.handle_revenuecat_transfer(
                session,
                settings,
                new_app_user_id="not-a-uuid",
                transferred_from=[],
            )

    apply_mock.assert_not_awaited()
    sync_mock.assert_not_awaited()
