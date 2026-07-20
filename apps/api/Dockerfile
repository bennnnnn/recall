# Recall API — production image.
# Deployed as two Fly processes from this one image (see fly.toml):
#   app    = FastAPI HTTP + WebSocket (PROCESS_ROLE=api)
#   worker = Redis-stream jobs + schedulers (PROCESS_ROLE=worker)
# The worker exposes a tiny /health/ready HTTP server on port 8001 so Fly can
# health-check it. Do NOT deploy to a serverless function platform — the worker
# and WS connections need a persistent process.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1

# Build deps for asyncpg/cryptography wheels (most ship manylinux; this covers any
# platform-specific builds). curl is for Fly's health checks.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade uv

WORKDIR /app

# Install dependencies first (better layer caching — app code changes more often).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# App + Alembic. alembic.ini and alembic/ are needed for migrations.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Run as non-root. Own the app tree + venv so alembic/uv can read/execute;
# /tmp stays world-writable for any scratch files.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app /opt/venv
USER appuser

EXPOSE 8000

# Migrate on every deploy, then start. The migration is idempotent (alembic
# upgrade head is a no-op when already at head). If migrate fails, the app
# doesn't start — better than serving against a stale schema.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
