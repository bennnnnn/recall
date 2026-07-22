import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:dev@localhost:5432/recall"
    redis_url: str = "redis://localhost:6379"

    google_client_id: str = ""
    google_client_secret: str = ""
    apple_client_id: str = "com.recall.app"

    jwt_secret: str = "dev-secret-change-me"
    # 60m is intentional: jti + revoked_since cover logout/reuse; lower freely
    # via env without schema changes if you want a shorter window.
    jwt_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30

    deepseek_api_key: str = ""  # legacy — unused; all models route via OpenRouter
    openrouter_api_key: str = ""
    tavily_api_key: str = ""

    google_calendar_enabled: bool = True
    calendar_cache_ttl: int = 300
    calendar_fetch_days: int = 60
    calendar_prompt_days: int = 14
    # A user can have many selected Google calendars (shared/subscribed);
    # both cap how many are fetched per refresh and bound how many of those
    # fetches run concurrently, so one user with dozens of calendars can't
    # fan out unboundedly.
    calendar_max_calendars: int = 10
    calendar_fetch_concurrency: int = 5
    calendar_nudge_enabled: bool = True
    calendar_nudge_lead_minutes: int = 15

    gmail_enabled: bool = True
    gmail_fetch_days: int = 7
    gmail_max_messages: int = 30
    gmail_cache_ttl: int = 300
    gmail_sync_interval_seconds: int = 3600
    # How many users' Gmail accounts the periodic sync cycle syncs concurrently
    # (each has its own DB session and outbound Gmail API calls).
    gmail_periodic_sync_concurrency: int = 5

    attachments_enabled: bool = True
    # PDF/DOCX text extraction is sync, CPU-bound parsing; it runs on a worker
    # thread (like the SymPy math solve) bounded by this timeout so a large or
    # adversarially crafted file can't block the event loop.
    attachment_extract_timeout_seconds: float = 5.0
    semantic_memory_enabled: bool = True
    mcp_tools_enabled: bool = False
    # Model-initiated LiteLLM tools= loop (bounded rounds before stream).
    # When on, skips heuristic pre-stream MCP + web-search injection for that turn.
    mcp_tool_loop_enabled: bool = False
    mcp_tool_loop_max_rounds: int = 3
    mcp_tool_loop_timeout_seconds: float = 30.0

    # Attachment RAG (chunk + embed PDF/doc text; retrieve into prompt).
    attachment_rag_enabled: bool = True
    attachment_rag_chunk_limit: int = 6
    attachment_rag_min_similarity: float = 0.25
    attachment_rag_chunk_chars: int = 900
    attachment_rag_chunk_overlap: int = 120
    attachment_rag_max_chunks_per_file: int = 40

    # Daily image-upload cap (per user, UTC day). Vision/image inputs cost more
    # than text, so cap uploads separately from the token quota. Enforced at
    # presign so a user can't accumulate uploads past the limit.
    daily_image_limit: int = 5
    daily_image_limit_pro: int = 30
    # Per-image token reserve added to the quota reservation for vision turns,
    # so a near-limit user can't start a heavy image call that blows past the
    # daily cap. Real usage is still reconciled from the provider's usage chunk.
    image_attachment_reserve_tokens: int = 1200
    # Orphan attachment reaper: delete bytes + rows for attachments never linked
    # to a message (e.g. uploaded then the send failed, or unlinked by a message
    # delete) once they're older than this grace window.
    attachment_orphan_grace_hours: int = 24
    attachment_orphan_reaper_interval_seconds: int = 3600

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
    # Dense enough for a smooth SVG polyline; larger dumps (300+) blow up
    # chat bubbles and FallbackMarkdown when the rich renderer dies.
    math_graph_max_points: int = 96
    # SymPy solve/simplify/integrate run on a worker thread (they're sync, CPU-bound);
    # this bounds how long a single pathological expression can occupy that thread
    # before the chat turn falls back to an unverified reply.
    math_solve_timeout_seconds: float = 5.0
    # math_image_extract.py's vision-chat call is a network round trip, not
    # local synchronous SymPy work — reusing math_solve_timeout_seconds's 5s
    # budget (sized for CPU-bound solve/integrate) cut off OCR calls that
    # were still legitimately in flight.
    math_image_extract_timeout_seconds: float = 20.0

    # Background LLM resilience: if the primary memory-model provider is down,
    # retry background jobs (memory/todo/project extraction, titles, summaries)
    # once against this alias. Empty disables the fallback.
    memory_fallback_model_alias: str = "fallback-memory-model"

    web_search_enabled: bool = True
    web_search_classifier_enabled: bool = True
    # Foreground TTFT path — keep this short; no model-fallback retry on timeout.
    web_search_classifier_timeout_seconds: float = 4.0
    web_search_fallback_enabled: bool = True
    web_search_max_results: int = 5
    web_search_cache_ttl: int = 300
    # Paid Tavily queries per user per UTC day; when exceeded, fall back to DuckDuckGo.
    daily_tavily_searches: int = 20
    daily_tavily_searches_pro: int = 150

    # Process role for production split: all (dev), api (HTTP only), worker (jobs only).
    process_role: str = "all"
    # Max in-flight jobs per worker process when draining a Redis Stream batch.
    # Keeps LLM handlers from head-of-line-blocking compress/topic/todo jobs.
    jobs_worker_concurrency: int = 8
    # Port the worker process exposes a tiny /health/ready endpoint on, so Fly
    # can health-check + auto-restart a stuck worker (the worker otherwise has
    # no HTTP). 0 disables the worker health server (e.g. process_role=all dev).
    worker_health_port: int = 8001
    speech_transcription_enabled: bool = True
    speech_transcription_model: str = "openai/whisper-1"
    speech_rate_limit_per_minute: int = 10
    daily_speech_transcriptions: int = 30
    daily_speech_transcriptions_pro: int = 200
    # Cloud TTS (read-aloud). Product alias conceptually `tts-model`; provider
    # mapping stays in speech.py (same pattern as Whisper).
    speech_tts_enabled: bool = True
    # OpenRouter requires the dated snapshot slug; bare gpt-4o-mini-tts 404s.
    speech_tts_model: str = "openai/gpt-4o-mini-tts-2025-12-15"
    speech_tts_voice: str = "alloy"
    daily_speech_tts: int = 20
    daily_speech_tts_pro: int = 100

    image_generation_enabled: bool = True
    image_generation_model: str = "black-forest-labs/flux.2-klein-4b"
    daily_image_generations: int = 0
    daily_image_generations_pro: int = 10

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
    # Opt-in todo-due / learning nudge emails (separate from welcome/receipt).
    email_reminders_scheduler_enabled: bool = True
    resend_api_key: str = ""
    resend_api_url: str = "https://api.resend.com/emails"
    email_from: str = "Recall <noreply@recall.app>"

    daily_token_limit: int = 100_000
    daily_token_limit_pro: int = 500_000
    max_output_tokens: int = 1200
    recent_message_window: int = 20  # hard cap on verbatim messages

    # Per-instance DB pool. Keep (db_pool_size + db_max_overflow) * INSTANCE_COUNT
    # under the Neon pooler connection ceiling. The chat hot path opens several
    # short-lived sessions per turn (context gather), so undersizing stalls TTFT
    # on SQLAlchemy's default 30s pool_timeout.
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout_seconds: float = 5.0
    # Cap concurrent DB checkouts inside the context gather so one turn cannot
    # grab all five pool slots at once.
    context_db_concurrency: int = 3
    memory_min_confidence: float = 0.4
    memory_inject_limit: int = 15
    # Hard cap on formatted memory block chars injected into the system prompt.
    memory_inject_max_chars: int = 1500
    memory_cache_ttl: int = 300
    memory_query_cache_ttl: int = 120
    # Run memory extraction every N completed assistant turns (always runs on turn 1).
    # Default 1 = every turn — sparse extraction missed durable facts between batches.
    memory_extract_every_n_turns: int = 1
    memory_query_embed_cache_ttl: int = 3600
    # Provider embedding-input char cap (embedding_gateway.embed_text). Was a
    # bare `text[:8000]` inline in the gateway; every other tunable in this
    # codebase lives in Settings, so don't reintroduce an inline magic number
    # here — change this constant instead.
    embedding_input_max_chars: int = 8000
    link_preview_cache_ttl: int = 3600
    home_cache_ttl: int = 120
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
    # Only trust X-Forwarded-For when deployed behind a known reverse proxy (Fly, etc.).
    trust_x_forwarded_for: bool = False
    # Peer CIDRs allowed to append X-Forwarded-For (private/LB ranges by default).
    # Include Fly 6PN (fdaa::/16) so IPv6 mesh peers are trusted when XFF is on.
    trusted_proxy_cidrs: str = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1/32,fdaa::/16"
    # Comma-separated user UUIDs allowed to access /admin/* when dev_auth is on.
    admin_user_ids: str = ""
    # Minimum cosine similarity for fact/focus/project injection (0 = disabled).
    # profile/preference always inject; 0.35 keeps off-topic sections out.
    memory_min_similarity: float = 0.35

    # Abort hung provider streams after this many seconds with no new chunk
    # (idle timeout). A long healthy reply can exceed this wall-clock total —
    # only silence between tokens trips it.
    chat_stream_timeout_seconds: int = 180
    # Fail fast when the provider never opens an SSE stream (separate from read timeout).
    chat_stream_connect_timeout_seconds: int = 15

    # Prefer Neon's `-pooler` host when DATABASE_URL points at a direct Neon endpoint.
    database_prefer_neon_pooler: bool = True

    # Abort hung background (non-streaming) LLM calls after this many seconds.
    # Covers title generation, memory extraction, todos, summaries — a hung
    # provider would otherwise stall the job worker indefinitely.
    background_llm_timeout_seconds: int = 60

    # Per-user/IP REST requests per minute (health + webhooks excluded).
    rest_rate_limit_per_minute: int = 240

    # Fernet key used to encrypt OAuth refresh tokens (Calendar/Gmail) at rest.
    # Generate one:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # When empty in development, tokens are stored plaintext (with a warning).
    # Required in production (see validate_production_settings).
    oauth_token_encryption_key: str = ""

    # Dev placeholders — disable in production.
    # ``environment`` defaults to production (fail-closed): a deploy that forgets
    # ENVIRONMENT=development boots into validate_production_settings instead of
    # leaving auth/LLM/CORS open. Local `.env` / `.env.example` set development.
    dev_auth_enabled: bool = True
    mock_llm_enabled: bool = True
    environment: str = "production"
    # Dev auth mints accounts without a provider token. Even when
    # ENVIRONMENT=development is set on a host, /auth/dev refuses non-loopback
    # callers unless this is explicitly true — so a dev-config accidentally
    # deployed to a public host cannot be turned into an account-takeover
    # endpoint. Set true ONLY for local tunnel testing.
    dev_auth_allow_remote: bool = False
    # RevenueCat webhooks require a shared secret. In dev with no secret
    # configured, the webhook is 503 by default; set this true ONLY when
    # testing locally so a missing secret never silently accepts webhooks on
    # a non-production host (environment alone must not skip auth).
    dev_allow_unauthed_webhooks: bool = False

    # Optional Sentry error reporting (leave empty to disable).
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1


def _trusted_proxy_cidrs_ipv4_only(cidrs: str) -> bool:
    """True when every non-empty CIDR parses as IPv4 (Fly 6PN would be ignored)."""
    import ipaddress

    parsed: list[bool] = []
    for raw in cidrs.split(","):
        piece = raw.strip()
        if not piece:
            continue
        try:
            net = ipaddress.ip_network(piece, strict=False)
        except ValueError:
            continue
        parsed.append(isinstance(net, ipaddress.IPv4Network))
    return bool(parsed) and all(parsed)


def _warn_proxy_trust_misconfig(settings: Settings) -> None:
    if not settings.trust_x_forwarded_for:
        return
    if not settings.trusted_proxy_cidrs.strip():
        logger.warning(
            "TRUST_X_FORWARDED_FOR=true but TRUSTED_PROXY_CIDRS is empty — "
            "client IPs will not use XFF / Fly-Client-IP."
        )
        return
    if _trusted_proxy_cidrs_ipv4_only(settings.trusted_proxy_cidrs):
        logger.warning(
            "TRUST_X_FORWARDED_FOR=true with IPv4-only TRUSTED_PROXY_CIDRS — "
            "Fly 6PN peers (fdaa::/16) will not be trusted; per-IP rate limits "
            "may collapse. Add fdaa::/16 (included in the default)."
        )


def validate_production_settings(settings: Settings) -> None:
    if settings.environment == "development":
        # Don't fully fail-closed in dev, but surface dangerous combos so a
        # dev config accidentally exposed publicly is visible in the logs.
        # The hard protection is the loopback guard on /auth/dev (see
        # routers/auth.py) — this warning is defense-in-depth visibility.
        if settings.dev_auth_enabled and settings.dev_auth_allow_remote:
            logger.warning(
                "DEV_AUTH_ALLOW_REMOTE=true with dev auth enabled — /auth/dev "
                "will mint accounts for non-loopback callers. Never set on a "
                "shared/hosted host."
            )
        if settings.dev_allow_unauthed_webhooks:
            logger.warning(
                "DEV_ALLOW_UNAUTHED_WEBHOOKS=true — RevenueCat webhooks will be "
                "accepted with no shared secret. Local testing only."
            )
        _warn_proxy_trust_misconfig(settings)
        return

    _warn_proxy_trust_misconfig(settings)

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
    if not settings.google_client_secret.strip():
        errors.append("GOOGLE_CLIENT_SECRET is required in production (Calendar/Gmail OAuth)")
    # CORS must be explicit in production — empty CORS_ORIGINS makes
    # cors_allow_origins() fall back to ["*"], which is unsafe once a web
    # client exists. Keep the fallback and this guard in the same module.
    if not settings.cors_origins.strip():
        errors.append("CORS_ORIGINS must be set to an explicit origin list in production")
    elif any(origin.strip() == "*" for origin in settings.cors_origins.split(",")):
        errors.append("CORS_ORIGINS must not include wildcard (*) in production")
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
    else:
        # Presence isn't enough — a malformed key only blows up on the first
        # encrypt/decrypt at runtime. Validate it parses as a real Fernet key
        # at boot so a bad deploy fails fast instead of mid-request.
        try:
            from cryptography.fernet import Fernet

            Fernet(settings.oauth_token_encryption_key.strip().encode())
        except Exception as exc:  # any Fernet parse failure is fatal at boot
            errors.append(
                "OAUTH_TOKEN_ENCRYPTION_KEY is not a valid Fernet key "
                '(generate with: python -c "from cryptography.fernet import Fernet; '
                f'print(Fernet.generate_key().decode())"): {exc}'
            )
    if settings.storage_backend.strip().lower() != "r2":
        errors.append("STORAGE_BACKEND must be r2 in production (local disk is ephemeral on Fly)")
    elif not all(
        [
            settings.r2_account_id.strip(),
            settings.r2_access_key_id.strip(),
            settings.r2_secret_access_key.strip(),
            settings.r2_bucket.strip(),
        ]
    ):
        errors.append(
            "R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_BUCKET "
            "are required when STORAGE_BACKEND=r2"
        )

    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


def cors_allow_origins(settings: Settings) -> list[str]:
    """Origins for CORSMiddleware.

    Empty ``CORS_ORIGINS`` falls back to ``["*"]`` for local dev. Production
    forbids empty and wildcard via :func:`validate_production_settings`.
    """
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    return origins or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
