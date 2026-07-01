from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:dev@localhost:5432/recall"
    redis_url: str = "redis://localhost:6379"

    google_client_id: str = ""
    google_client_secret: str = ""

    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 60 * 24 * 7

    deepseek_api_key: str = ""  # legacy — unused; all models route via OpenRouter
    openrouter_api_key: str = ""
    tavily_api_key: str = ""

    google_calendar_enabled: bool = True
    calendar_cache_ttl: int = 300
    calendar_fetch_days: int = 60
    calendar_prompt_days: int = 14

    gmail_enabled: bool = True
    gmail_fetch_days: int = 7
    gmail_max_messages: int = 30
    gmail_cache_ttl: int = 300
    gmail_sync_interval_seconds: int = 3600

    attachments_enabled: bool = True
    semantic_memory_enabled: bool = True
    mcp_tools_enabled: bool = False

    # Object storage for attachments. ``local`` writes to disk (dev);
    # ``r2`` presigns Cloudflare R2 (S3-compatible) URLs so the client uploads/
    # downloads directly — blobs never touch the API. R2 creds come from the
    # r2_* settings below; when missing in dev we fall back to local.
    storage_backend: str = "local"
    storage_local_path: str = "/tmp/recall-attachments"  # noqa: S108  # dev default; overridden in prod
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_endpoint: str = ""  # derived from account_id if empty
    r2_presign_expiry_seconds: int = 600

    math_tools_enabled: bool = True
    math_max_expr_length: int = 256
    math_graph_max_points: int = 300

    web_search_enabled: bool = True
    web_search_fallback_enabled: bool = True
    web_search_max_results: int = 5
    web_search_cache_ttl: int = 300

    push_enabled: bool = True
    push_learning_hour: int = 9
    server_todo_push_enabled: bool = False  # local notifications handle todo reminders

    revenuecat_secret_key: str = ""
    revenuecat_webhook_auth: str = ""
    revenuecat_entitlement_id: str = "pro"

    # Transactional email (welcome / receipts). Provider is Resend when
    # `resend_api_key` is set; otherwise a mock that logs the message so dev
    # works with zero external setup. Sending is always best-effort via the
    # background jobs stream — it never blocks auth or the chat path.
    email_enabled: bool = True
    resend_api_key: str = ""
    resend_api_url: str = "https://api.resend.com/emails"
    email_from: str = "Recall <noreply@recall.app>"

    daily_token_limit: int = 30_000
    daily_token_limit_pro: int = 500_000
    max_output_tokens: int = 1200
    recent_message_window: int = 40  # hard cap on verbatim messages
    memory_min_confidence: float = 0.4
    memory_inject_limit: int = 15
    memory_cache_ttl: int = 300
    memory_query_cache_ttl: int = 120
    todo_inject_limit: int = 100
    todo_prompt_limit: int = 48
    project_inject_limit: int = 50
    project_item_inject_limit: int = 300

    # History compression — keep recent turns verbatim within a token budget,
    # summarise everything older.
    history_compression_enabled: bool = True
    context_token_budget: int = 6000
    history_summary_batch: int = 10
    history_summary_urgent_pending: int = 3
    summary_max_tokens: int = 400

    cors_origins: str = ""

    # Fernet key used to encrypt OAuth refresh tokens (Calendar/Gmail) at rest.
    # Generate one:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # When empty in development, tokens are stored plaintext (with a warning).
    # Required in production (see validate_production_settings).
    oauth_token_encryption_key: str = ""

    # Dev placeholders — disable in production
    dev_auth_enabled: bool = True
    mock_llm_enabled: bool = True
    environment: str = "development"


def validate_production_settings(settings: Settings) -> None:
    if settings.environment == "development":
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
    # CORS must be explicit in production — an empty CORS_ORIGINS makes the API
    # accept any origin (main.py falls back to ["*"]), which contradicts the
    # "locked-down CORS" claim and is unsafe once a web client exists.
    if not settings.cors_origins.strip():
        errors.append("CORS_ORIGINS must be set to an explicit origin list in production")
    # Without a real model key the app boots but every chat call fails at runtime
    # with a generic ModelUnavailableError — fail fast at startup instead.
    if not settings.openrouter_api_key:
        errors.append("OPENROUTER_API_KEY is required in production (chat would otherwise fail)")
    # Unsigned RevenueCat webhooks would let anyone grant themselves Pro.
    if not settings.revenuecat_webhook_auth:
        errors.append("REVENUECAT_WEBHOOK_AUTH is required in production")
    # OAuth refresh tokens (Calendar/Gmail) must be encrypted at rest — a DB
    # leak shouldn't expose reusable Google OAuth tokens.
    if not settings.oauth_token_encryption_key:
        errors.append(
            "OAUTH_TOKEN_ENCRYPTION_KEY is required in production "
            '(generate with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())")'
        )

    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
