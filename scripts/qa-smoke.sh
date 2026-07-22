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

echo "==> Alembic has a single head"
if command -v uv >/dev/null 2>&1; then
  HEADS_OUT="$(
    cd "$ROOT/apps/api" && uv run alembic heads 2>/dev/null || true
  )"
  HEAD_COUNT="$(printf '%s\n' "$HEADS_OUT" | rg -c '\(head\)' || true)"
  if [[ "${HEAD_COUNT:-0}" == "1" ]]; then
    echo "    OK: $(printf '%s\n' "$HEADS_OUT" | head -1)"
  else
    echo "    FAIL: expected exactly one alembic head, got:"
    printf '%s\n' "${HEADS_OUT:-<empty>}" | sed 's/^/      /'
    fail=1
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
  STORAGE_BACKEND
  R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET
)
env_fail=0
for key in "${REQUIRED_KEYS[@]}"; do
  if ! rg -q "^${key}=" "$ROOT/apps/api/.env.example"; then
    echo "    FAIL: missing $key in apps/api/.env.example"
    env_fail=1
  fi
done
if [[ "$env_fail" -eq 0 ]]; then
  echo "    OK"
else
  fail=1
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
