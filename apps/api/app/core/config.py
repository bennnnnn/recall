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

    cors_origins: str = ""

    # Dev placeholders — disable in production
    dev_auth_enabled: bool = True
    mock_llm_enabled: bool = True
    environment: str = "development"


def validate_production_settings(settings: Settings) -> None:
    if settings.environment != "production":
        return

    errors: list[str] = []
    if settings.dev_auth_enabled:
        errors.append("DEV_AUTH_ENABLED must be false in production")
    if settings.mock_llm_enabled:
        errors.append("MOCK_LLM_ENABLED must be false in production")
    if settings.jwt_secret == "dev-secret-change-me" or len(settings.jwt_secret) < 32:
        errors.append("JWT_SECRET must be a strong secret in production")
    if not settings.database_url:
        errors.append("DATABASE_URL is required in production")
    if not settings.redis_url:
        errors.append("REDIS_URL is required in production")
    if not settings.google_client_id:
        errors.append("GOOGLE_CLIENT_ID is required in production")

    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
