from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services import google_integrations as google_integrations_service


@pytest.mark.asyncio
async def test_revoke_on_disconnect_calendar_skips_shared_token():
    user_id = uuid4()
    session = AsyncMock()
    settings = Settings()
    calendar = MagicMock(refresh_token="enc-cal")
    gmail = MagicMock(refresh_token="enc-gmail")

    with (
        patch(
            "app.services.google_integrations.calendar_repo.get_for_user",
            AsyncMock(return_value=calendar),
        ),
        patch(
            "app.services.google_integrations.gmail_repo.get_for_user",
            AsyncMock(return_value=gmail),
        ),
        patch(
            "app.services.google_integrations.decrypt_refresh_token",
            side_effect=lambda _s, token: "shared-token" if token else "",
        ),
        patch(
            "app.services.google_integrations.google_oauth_revoke.revoke_refresh_token",
            AsyncMock(),
        ) as revoke_mock,
    ):
        await google_integrations_service.revoke_on_disconnect(
            session,
            settings,
            user_id,
            disconnect="calendar",
        )

    revoke_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_on_disconnect_calendar_revokes_unique_token():
    user_id = uuid4()
    session = AsyncMock()
    settings = Settings()
    calendar = MagicMock(refresh_token="enc-cal")

    with (
        patch(
            "app.services.google_integrations.calendar_repo.get_for_user",
            AsyncMock(return_value=calendar),
        ),
        patch(
            "app.services.google_integrations.gmail_repo.get_for_user",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.google_integrations.decrypt_refresh_token",
            return_value="calendar-only-token",
        ),
        patch(
            "app.services.google_integrations.google_oauth_revoke.revoke_refresh_token",
            AsyncMock(return_value=True),
        ) as revoke_mock,
    ):
        await google_integrations_service.revoke_on_disconnect(
            session,
            settings,
            user_id,
            disconnect="calendar",
        )

    revoke_mock.assert_awaited_once_with("calendar-only-token")


@pytest.mark.asyncio
async def test_revoke_all_google_tokens_dedupes_shared_refresh():
    user_id = uuid4()
    session = AsyncMock()
    settings = Settings()
    calendar = MagicMock(refresh_token="enc-cal")
    gmail = MagicMock(refresh_token="enc-gmail")

    with (
        patch(
            "app.services.google_integrations.calendar_repo.get_for_user",
            AsyncMock(return_value=calendar),
        ),
        patch(
            "app.services.google_integrations.gmail_repo.get_for_user",
            AsyncMock(return_value=gmail),
        ),
        patch(
            "app.services.google_integrations.decrypt_refresh_token",
            return_value="shared-token",
        ),
        patch(
            "app.services.google_integrations.google_oauth_revoke.revoke_refresh_token",
            AsyncMock(return_value=True),
        ) as revoke_mock,
    ):
        await google_integrations_service.revoke_all_google_tokens_for_user(
            session,
            settings,
            user_id,
        )

    revoke_mock.assert_awaited_once_with("shared-token")


@pytest.mark.asyncio
async def test_google_oauth_revoke_accepts_success():
    from app.gateways import google_oauth_revoke

    class FakeResponse:
        status_code = 200
        text = ""

    with patch(
        "app.gateways.google_oauth_revoke.httpx.AsyncClient",
    ) as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post = AsyncMock(return_value=FakeResponse())
        client_cls.return_value = client

        ok = await google_oauth_revoke.revoke_refresh_token("refresh-token")

    assert ok is True
    client.post.assert_awaited_once()
