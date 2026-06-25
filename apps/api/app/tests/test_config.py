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
            )
        )


@pytest.mark.asyncio
async def test_allow_request(fake_redis):
    assert await allow_request(fake_redis, "rate:test", limit=2, window_seconds=60) is True
    assert await allow_request(fake_redis, "rate:test", limit=2, window_seconds=60) is True
    assert await allow_request(fake_redis, "rate:test", limit=2, window_seconds=60) is False
