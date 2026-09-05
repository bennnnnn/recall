#!/usr/bin/env bash
#
# Per-boot startup for the Recall Cloud Agent environment.
#
# Brings up the local infrastructure the backend needs and reconciles dev
# config so a freshly booted agent can immediately run the API + web client:
#   - PostgreSQL 16 (with the pgvector extension) on 127.0.0.1:5432
#   - Redis on 127.0.0.1:6379
#   - apps/api/.env, apps/web/.env, apps/mobile/.env (dev auth + mock LLM)
#   - the `recall` database, the `vector` extension, and migrations at head
#
# Idempotent and safe to run repeatedly: it detects already-running services,
# only creates missing state, and treats "already at head" migrations as a
# no-op. It never depends on files created only by an unmerged setup PR.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

PG_MAJOR=16
DB_NAME=recall
DB_USER=postgres
DB_PASSWORD=postgres

log() { echo "==> $*"; }

ensure_env_file() {
  # $1 = target .env, $2 = example, remaining args = KEY=VALUE overrides.
  local target="$1" example="$2"
  shift 2
  if [ ! -f "$target" ] && [ -f "$example" ]; then
    cp "$example" "$target"
  fi
  [ -f "$target" ] || return 0
  local pair key value
  for pair in "$@"; do
    key="${pair%%=*}"
    value="${pair#*=}"
    if grep -qE "^${key}=" "$target"; then
      # Use a Python rewrite so values with slashes/special chars are safe.
      KEY="$key" VALUE="$value" TARGET="$target" python3 - <<'PY'
import os, re, pathlib
p = pathlib.Path(os.environ["TARGET"])
key, value = os.environ["KEY"], os.environ["VALUE"]
text = p.read_text()
text = re.sub(rf"^{re.escape(key)}=.*$", f"{key}={value}", text, flags=re.M)
p.write_text(text)
PY
    else
      printf '%s=%s\n' "$key" "$value" >> "$target"
    fi
  done
}

ensure_secret_env() {
  # Generate a JWT secret + Fernet OAuth key once, only if still placeholder.
  local target="$ROOT/apps/api/.env"
  [ -f "$target" ] || return 0
  if grep -qE '^JWT_SECRET=(change-me-in-production)?$' "$target"; then
    ensure_env_file "$target" "$target" \
      "JWT_SECRET=$(python3 -c 'import base64,secrets;print(base64.b64encode(secrets.token_bytes(32)).decode())')"
  fi
  if grep -qE '^OAUTH_TOKEN_ENCRYPTION_KEY=$' "$target"; then
    ensure_env_file "$target" "$target" \
      "OAUTH_TOKEN_ENCRYPTION_KEY=$(python3 -c 'import base64,secrets;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')"
  fi
}

log "[1/5] Ensuring dev .env files"
ensure_env_file "$ROOT/apps/api/.env" "$ROOT/apps/api/.env.example" \
  "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}" \
  "REDIS_URL=redis://localhost:6379" \
  "CORS_ORIGINS=http://localhost:5173" \
  "DEV_AUTH_ENABLED=true" \
  "MOCK_LLM_ENABLED=true" \
  "ENVIRONMENT=development"
ensure_secret_env
ensure_env_file "$ROOT/apps/web/.env" "$ROOT/apps/web/.env.example" \
  "VITE_API_URL=http://localhost:8000"
ensure_env_file "$ROOT/apps/mobile/.env" "$ROOT/apps/mobile/.env.example" \
  "EXPO_PUBLIC_API_URL=http://localhost:8000" \
  "EXPO_PUBLIC_DEV_AUTH_ENABLED=true"

log "[2/5] Starting PostgreSQL ${PG_MAJOR}"
if ! pg_isready -h 127.0.0.1 -p 5432 -q 2>/dev/null; then
  # The apt package creates the `main` cluster; initialize it if absent.
  if [ ! -d "/etc/postgresql/${PG_MAJOR}/main" ]; then
    sudo pg_createcluster "${PG_MAJOR}" main
  fi
  sudo pg_ctlcluster "${PG_MAJOR}" main start
fi
for _ in $(seq 1 30); do
  pg_isready -h 127.0.0.1 -p 5432 -q 2>/dev/null && break
  sleep 1
done
pg_isready -h 127.0.0.1 -p 5432 -q

log "[3/5] Ensuring role, database, and pgvector extension"
sudo -u postgres psql -v ON_ERROR_STOP=1 -qtAc \
  "ALTER USER ${DB_USER} PASSWORD '${DB_PASSWORD}';" >/dev/null
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  sudo -u postgres createdb "${DB_NAME}"
fi
sudo -u postgres psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -qtAc \
  "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null

log "[4/5] Starting Redis"
if ! redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG; then
  sudo mkdir -p /var/lib/redis
  sudo redis-server --daemonize yes --port 6379 --dir /var/lib/redis
  for _ in $(seq 1 15); do
    redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG && break
    sleep 1
  done
fi
redis-cli -h 127.0.0.1 -p 6379 ping | grep -q PONG

log "[5/5] Applying database migrations (alembic upgrade head)"
if command -v uv >/dev/null 2>&1 && [ -d "$ROOT/apps/api/.venv" ]; then
  (cd "$ROOT/apps/api" && uv run alembic upgrade head)
else
  echo "    Skipping migrations (uv/.venv not ready yet; install will run them)."
fi

log "Recall dev services are up (PostgreSQL:5432, Redis:6379)."
