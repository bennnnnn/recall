#!/usr/bin/env bash
#
# Automated smoke checks — backend health, migration head, local gate optional.
# Does not replace on-device QA (see docs/QA_MATRIX.md).
#
# Usage:
#   ./scripts/qa-smoke.sh              # static checks only
#   ./scripts/qa-smoke.sh --live       # also hit API health (API must be running)
#   API_URL=https://api.example.com ./scripts/qa-smoke.sh --live
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_URL="${API_URL:-http://127.0.0.1:8000}"
LIVE=0
if [[ "${1:-}" == "--live" ]]; then
  LIVE=1
fi

fail=0

echo "==> Migration head is 0036"
HEAD_FILE="$ROOT/apps/api/alembic/versions/0036_builtin_template_title_unique.py"
if [[ ! -f "$HEAD_FILE" ]]; then
  echo "    FAIL: expected $HEAD_FILE"
  fail=1
else
  if ! rg -q 'revision: str = "0036"' "$HEAD_FILE"; then
    echo "    FAIL: 0036 revision id mismatch"
    fail=1
  else
    echo "    OK"
  fi
fi

echo "==> Alembic reports head 0036 (needs DATABASE_URL in apps/api/.env)"
if command -v uv >/dev/null 2>&1; then
  if (
    cd "$ROOT/apps/api" &&
      uv run alembic heads 2>/dev/null | rg -q '0036'
  ); then
    echo "    OK"
  else
    echo "    WARN: could not confirm alembic head (set DATABASE_URL and run ./scripts/dev.sh migrate)"
  fi
else
  echo "    WARN: uv not found — skipped"
fi

echo "==> Production env template covers required keys"
REQUIRED_KEYS=(
  ENVIRONMENT
  DATABASE_URL
  REDIS_URL
  JWT_SECRET
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  OPENROUTER_API_KEY
  CORS_ORIGINS
  OAUTH_TOKEN_ENCRYPTION_KEY
  REVENUECAT_WEBHOOK_AUTH
)
for key in "${REQUIRED_KEYS[@]}"; do
  if ! rg -q "^${key}=" "$ROOT/apps/api/.env.example"; then
    echo "    FAIL: missing $key in apps/api/.env.example"
    fail=1
  fi
done
if [[ "$fail" -eq 0 ]]; then
  echo "    OK"
fi

if [[ "$LIVE" -eq 1 ]]; then
  echo "==> Live health: $API_URL/health"
  if curl -sf "$API_URL/health" | rg -q '"status".*"ok"'; then
    echo "    OK"
  else
    echo "    FAIL: GET /health"
    fail=1
  fi

  echo "==> Live readiness: $API_URL/health/ready"
  if curl -sf "$API_URL/health/ready" | rg -q '"status".*"ok"'; then
    echo "    OK"
  else
    echo "    FAIL: GET /health/ready (is API up with DB + Redis?)"
    fail=1
  fi
fi

if [[ "$fail" -ne 0 ]]; then
  echo ""
  echo "FAIL: smoke checks failed"
  exit 1
fi

echo ""
echo "OK: smoke checks passed"
if [[ "$LIVE" -eq 0 ]]; then
  echo "Tip: start API and run ./scripts/qa-smoke.sh --live"
fi
