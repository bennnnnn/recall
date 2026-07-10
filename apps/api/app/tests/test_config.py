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
            google_client_secret="client-secret",
            cors_origins="https://app.recall.app",
            openrouter_api_key="sk-or-xxx",
            revenuecat_webhook_auth="whsec-xxx",
            oauth_token_encryption_key="a-fernet-key",
            storage_backend="r2",
            r2_account_id="acct",
            r2_access_key_id="key",
            r2_secret_access_key="secret",
            r2_bucket="recall",
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
        google_client_secret="secret",
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


def test_validate_production_settings_requires_r2():
    base = dict(
        environment="production",
        dev_auth_enabled=False,
        mock_llm_enabled=False,
        jwt_secret="super-secret-key-that-is-at-least-32-chars!!",
        google_client_id="client-id",
        google_client_secret="secret",
        cors_origins="https://app.recall.app",
        openrouter_api_key="sk-or-xxx",
        revenuecat_webhook_auth="whsec-xxx",
        oauth_token_encryption_key="key",
    )
    with pytest.raises(RuntimeError, match="STORAGE_BACKEND"):
        validate_production_settings(Settings(**base, storage_backend="local"))
    with pytest.raises(RuntimeError, match="R2_ACCOUNT_ID"):
        validate_production_settings(
            Settings(**base, storage_backend="r2", r2_account_id="", r2_bucket="b")
        )


def test_validate_production_settings_skips_in_development():
    validate_production_settings(
        Settings(
            environment="development",
            dev_auth_enabled=True,
            mock_llm_enabled=True,
            jwt_secret="dev-secret-change-me",
        )
    )


def test_validate_production_settings_rejects_mock_llm_and_weak_jwt():
    base = dict(
        environment="production",
        dev_auth_enabled=False,
        google_client_id="client-id",
        google_client_secret="secret",
        cors_origins="https://app.recall.app",
        openrouter_api_key="sk-or-xxx",
        revenuecat_webhook_auth="whsec-xxx",
        oauth_token_encryption_key="key",
        storage_backend="r2",
        r2_account_id="acct",
        r2_access_key_id="key",
        r2_secret_access_key="secret",
        r2_bucket="recall",
    )
    with pytest.raises(RuntimeError, match="MOCK_LLM_ENABLED"):
        validate_production_settings(
            Settings(
                **base,
                mock_llm_enabled=True,
                jwt_secret="super-secret-key-that-is-at-least-32-chars!!",
            )
        )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_production_settings(Settings(**base, mock_llm_enabled=False, jwt_secret="short"))


def test_validate_production_settings_rejects_missing_core_urls():
    base = dict(
        environment="production",
        dev_auth_enabled=False,
        mock_llm_enabled=False,
        jwt_secret="super-secret-key-that-is-at-least-32-chars!!",
        google_client_id="client-id",
        google_client_secret="secret",
        cors_origins="https://app.recall.app",
        openrouter_api_key="sk-or-xxx",
        revenuecat_webhook_auth="whsec-xxx",
        oauth_token_encryption_key="key",
        storage_backend="r2",
        r2_account_id="acct",
        r2_access_key_id="key",
        r2_secret_access_key="secret",
        r2_bucket="recall",
    )
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        validate_production_settings(Settings(**base, database_url=""))
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        validate_production_settings(Settings(**base, redis_url=""))
    no_google = {k: v for k, v in base.items() if k != "google_client_id"}
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_ID"):
        validate_production_settings(Settings(**no_google, google_client_id=""))


def test_validate_production_settings_rejects_cors_wildcard():
    base = dict(
        environment="production",
        dev_auth_enabled=False,
        mock_llm_enabled=False,
        jwt_secret="super-secret-key-that-is-at-least-32-chars!!",
        google_client_id="client-id",
        google_client_secret="secret",
        openrouter_api_key="sk-or-xxx",
        revenuecat_webhook_auth="whsec-xxx",
        oauth_token_encryption_key="key",
        storage_backend="r2",
        r2_account_id="acct",
        r2_access_key_id="key",
        r2_secret_access_key="secret",
        r2_bucket="recall",
    )
    with pytest.raises(RuntimeError, match="wildcard"):
        validate_production_settings(Settings(**base, cors_origins="*"))


def test_validate_production_settings_requires_google_client_secret():
    base = dict(
        environment="production",
        dev_auth_enabled=False,
        mock_llm_enabled=False,
        jwt_secret="super-secret-key-that-is-at-least-32-chars!!",
        google_client_id="client-id",
        cors_origins="https://app.recall.app",
        openrouter_api_key="sk-or-xxx",
        revenuecat_webhook_auth="whsec-xxx",
        oauth_token_encryption_key="key",
        storage_backend="r2",
        r2_account_id="acct",
        r2_access_key_id="key",
        r2_secret_access_key="secret",
        r2_bucket="recall",
    )
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_SECRET"):
        validate_production_settings(Settings(**base, google_client_secret=""))
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_SECRET"):
        validate_production_settings(Settings(**base, google_client_secret="   "))


@pytest.mark.asyncio
async def test_allow_request(fake_redis):
    assert await allow_request(fake_redis, "rate:test", limit=2, window_seconds=60) is True
    assert await allow_request(fake_redis, "rate:test", limit=2, window_seconds=60) is True
    assert await allow_request(fake_redis, "rate:test", limit=2, window_seconds=60) is False


@pytest.mark.asyncio
async def test_allow_request_sets_ttl_on_first_hit(fake_redis):
    assert await allow_request(fake_redis, "rate:ttl", limit=5, window_seconds=90) is True
    assert await fake_redis.ttl("rate:ttl") == 90
    assert await allow_request(fake_redis, "rate:ttl", limit=5, window_seconds=90) is True
    # Subsequent hits must not refresh the window (EXPIRE NX).
    assert await fake_redis.ttl("rate:ttl") == 90
