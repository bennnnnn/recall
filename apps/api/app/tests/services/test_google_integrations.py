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


# ── connect_calendar: scope verification ──────────────────────────────────


@pytest.mark.asyncio
async def test_connect_calendar_rejects_missing_calendar_readonly_scope():
    """connect_calendar must require calendar.readonly in the granted scopes
    before upsert — mirroring Gmail's check. Without this, a user who grants
    only (e.g.) gmail.readonly via the calendar flow would be stored as
    'connected' with no calendar access, and every calendar fetch would 403."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "user@example.com"
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings()

    token_data = {
        "refresh_token": "rt-cal",
        "access_token": "at-cal",
        "scope": "https://www.googleapis.com/auth/gmail.readonly",  # wrong scope
    }

    with (
        patch(
            "app.services.google_integrations.exchange_server_auth_code",
            AsyncMock(return_value=token_data),
        ),
        patch(
            "app.services.google_integrations.calendar_repo.get_for_user",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.google_integrations._resolve_stored_refresh_token",
            return_value="enc-rt",
        ),
        patch(
            "app.services.google_integrations.google_oauth.fetch_google_email",
            AsyncMock(return_value="user@example.com"),
        ),
        patch(
            "app.services.google_integrations.calendar_repo.upsert",
            AsyncMock(),
        ) as upsert_mock,
    ):
        with pytest.raises(google_integrations_service.GoogleConnectError, match="Calendar read"):
            await google_integrations_service.connect_calendar(
                session, redis, settings, user, "server-auth-code"
            )

    upsert_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_calendar_accepts_calendar_readonly_scope():
    """When calendar.readonly IS granted, the connection is upserted."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "user@example.com"
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings()

    token_data = {
        "refresh_token": "rt-cal",
        "access_token": "at-cal",
        "scope": "https://www.googleapis.com/auth/calendar.readonly",
    }

    with (
        patch(
            "app.services.google_integrations.exchange_server_auth_code",
            AsyncMock(return_value=token_data),
        ),
        patch(
            "app.services.google_integrations.calendar_repo.get_for_user",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.google_integrations._resolve_stored_refresh_token",
            return_value="enc-rt",
        ),
        patch(
            "app.services.google_integrations.google_oauth.fetch_google_email",
            AsyncMock(return_value="user@example.com"),
        ),
        patch(
            "app.services.google_integrations.calendar_repo.upsert",
            AsyncMock(),
        ) as upsert_mock,
        patch(
            "app.services.google_integrations.calendar_service.clear_events_cache",
            AsyncMock(),
        ),
        patch(
            "app.services.google_integrations.home_service.invalidate_home_cache",
            AsyncMock(),
        ),
    ):
        result = await google_integrations_service.connect_calendar(
            session, redis, settings, user, "server-auth-code"
        )

    upsert_mock.assert_awaited_once()
    assert "calendar.readonly" in result.scopes
