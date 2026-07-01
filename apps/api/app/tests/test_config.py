import pytest

from app.core.config import Settings, validate_production_settings
from app.core.rate_limit import allow_request


def test_validate_production_settings_ok():
    validate_production_settings(
        Settings(
            environment="production",
            dev_auth_enabled=False,
            mock_llm_enabled=False,
            jwt_secret="super-secret-key-that-is-at-least-32-chars!!",
            google_client_id="client-id",
            cors_origins="https://app.recall.app",
            openrouter_api_key="sk-or-xxx",
            revenuecat_webhook_auth="whsec-xxx",
            oauth_token_encryption_key="a-fernet-key",
        )
    )


def test_validate_production_settings_rejects_dev_flags():
    with pytest.raises(RuntimeError, match="DEV_AUTH_ENABLED"):
        validate_production_settings(
            Settings(
                environment="production",
                dev_auth_enabled=True,
                mock_llm_enabled=False,
                jwt_secret="super-secret-key-that-is-at-least-32-chars!!",
                google_client_id="client-id",
                cors_origins="https://app.recall.app",
                openrouter_api_key="sk-or-xxx",
                revenuecat_webhook_auth="whsec-xxx",
            )
        )


def test_validate_production_settings_rejects_empty_cors_and_missing_secrets():
    base = dict(
        environment="production",
        dev_auth_enabled=False,
        mock_llm_enabled=False,
        jwt_secret="super-secret-key-that-is-at-least-32-chars!!",
        google_client_id="client-id",
    )
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_production_settings(
            Settings(
                **base,
                cors_origins="",
                openrouter_api_key="sk-or-xxx",
                revenuecat_webhook_auth="whsec-xxx",
            )
        )
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        validate_production_settings(
            Settings(
                **base,
                cors_origins="https://app.recall.app",
                openrouter_api_key="",
                revenuecat_webhook_auth="whsec-xxx",
            )
        )
    with pytest.raises(RuntimeError, match="REVENUECAT_WEBHOOK_AUTH"):
        validate_production_settings(
            Settings(
                **base,
                cors_origins="https://app.recall.app",
                openrouter_api_key="sk-or-xxx",
                revenuecat_webhook_auth="",
            )
        )
    with pytest.raises(RuntimeError, match="OAUTH_TOKEN_ENCRYPTION_KEY"):
        validate_production_settings(
            Settings(
                **base,
                cors_origins="https://app.recall.app",
                openrouter_api_key="sk-or-xxx",
                revenuecat_webhook_auth="whsec-xxx",
                oauth_token_encryption_key="",
            )
        )


@pytest.mark.asyncio
async def test_allow_request(fake_redis):
    assert await allow_request(fake_redis, "rate:test", limit=2, window_seconds=60) is True
    assert await allow_request(fake_redis, "rate:test", limit=2, window_seconds=60) is True
    assert await allow_request(fake_redis, "rate:test", limit=2, window_seconds=60) is False
