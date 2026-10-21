"""Where the process runs and what it connects to: environment, role, Postgres, Redis, Sentry."""

from pydantic import BaseModel


class InfrastructureSettings(BaseModel):
    database_url: str = "postgresql+asyncpg://postgres:dev@localhost:5432/recall"
    redis_url: str = "redis://localhost:6379"

    # Process role for production split: all (dev), api (HTTP only), worker (jobs only).
    process_role: str = "all"

    # Per-instance DB pool. Keep (db_pool_size + db_max_overflow) * INSTANCE_COUNT
    # under the Neon pooler connection ceiling. The chat hot path opens several
    # short-lived sessions per turn (context gather), so undersizing stalls TTFT
    # on SQLAlchemy's default 30s pool_timeout.
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout_seconds: float = 5.0
    # asyncpg connect timeout (default 60s) and per-statement timeout (default
    # none). Without a statement timeout one half-open pooled connection hung a
    # request forever (the checkout ping included). Generous: account delete is
    # one cascading DELETE. 0 disables.
    db_connect_timeout_seconds: float = 10.0
    db_command_timeout_seconds: float = 120.0
    # A pooled connection idle this long is pinged on checkout (three round
    # trips); one used more recently is trusted, and one the server closed is
    # replaced for free (core/pool_liveness.py). 0 pings every checkout, as
    # pool_pre_ping did. Well under Neon's 5 min suspend and NAT idle timeouts.
    db_idle_ping_seconds: float = 60.0
    # Each migration transaction's lock wait and statement limit (Postgres
    # durations; core/migration_session.py). Under Fly's 5 min release timeout.
    migration_lock_timeout: str = "5s"
    migration_statement_timeout: str = "4min"
    # Cap concurrent DB checkouts inside the context gather so one turn cannot
    # grab all five pool slots at once.
    context_db_concurrency: int = 3

    # Prefer Neon's `-pooler` host when DATABASE_URL points at a direct Neon endpoint.
    database_prefer_neon_pooler: bool = True
    # ``environment`` defaults to production (fail-closed): a deploy that forgets
    # ENVIRONMENT=development boots into validate_production_settings instead of
    # leaving auth/LLM/CORS open. Local `.env` / `.env.example` set development.
    environment: str = "production"

    # Optional Sentry error reporting (leave empty to disable).
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
