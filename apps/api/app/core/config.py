from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:dev@localhost:5432/recall"
    redis_url: str = "redis://localhost:6379"

    google_client_id: str = ""
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 60 * 24 * 7

    deepseek_api_key: str = ""
    openrouter_api_key: str = ""

    daily_token_limit: int = 30_000
    max_output_tokens: int = 1200
    recent_message_window: int = 20
    memory_min_confidence: float = 0.4
    memory_inject_limit: int = 15

    sentry_dsn: str = ""

    # Dev placeholders — disable in production
    dev_auth_enabled: bool = True
    mock_llm_enabled: bool = True
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
