#!/usr/bin/env bash
#
# Production readiness report — static validation + optional live API checks.
# Does not provision cloud resources; see docs/PRODUCTION.md.
#
# Usage:
#   ./scripts/verify-production.sh
#   API_URL=https://recall-api.fly.dev ./scripts/verify-production.sh --live
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_URL="${API_URL:-}"
LIVE=0
[[ "${1:-}" == "--live" ]] && LIVE=1

echo "=== Recall production verification ==="
echo ""

# Reuse smoke checks
if ! "$ROOT/scripts/qa-smoke.sh" $([[ "$LIVE" -eq 1 ]] && echo --live); then
  exit 1
fi

echo ""
echo "==> Fly.toml process split"
if rg -q 'PROCESS_ROLE = "api"' "$ROOT/fly.toml" && rg -q 'worker' "$ROOT/fly.toml"; then
  echo "    OK: app + worker processes defined"
else
  echo "    WARN: review fly.toml process configuration"
fi

echo ""
echo "==> Production settings validator exists"
if rg -q 'def validate_production_settings' "$ROOT/apps/api/app/core/config.py"; then
  echo "    OK"
else
  echo "    FAIL: validate_production_settings not found"
  exit 1
fi

echo ""
echo "==> Mobile EAS production profile"
if [[ -f "$ROOT/apps/mobile/eas.json" ]] && rg -q '"production"' "$ROOT/apps/mobile/eas.json"; then
  echo "    OK"
else
  echo "    WARN: review apps/mobile/eas.json"
fi

if [[ "$LIVE" -eq 1 && -n "$API_URL" ]]; then
  echo ""
  echo "==> CORS preflight (OPTIONS) — informational"
  ORIGIN="${CORS_TEST_ORIGIN:-https://app.recall.app}"
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS \
    -H "Origin: $ORIGIN" \
    -H "Access-Control-Request-Method: GET" \
    "$API_URL/health" || echo "000")
  echo "    OPTIONS /health from Origin $ORIGIN → HTTP $STATUS"
fi

echo ""
echo "=== Manual steps remaining ==="
echo "  • Install flyctl and authenticate: https://fly.io/docs/hands-on/install-flyctl/"
echo "  • Set Fly secrets (see docs/PRODUCTION.md §4) — app name: recall-api"
echo "  • fly scale count app=1 worker=1 && fly deploy"
echo "  • Provision R2 and set STORAGE_BACKEND=r2 (+ R2_* secrets)"
echo "  • EAS production builds + store submission"
echo "  • Complete docs/QA_MATRIX.md on physical devices"
echo "  • Google OAuth verification for Gmail"
echo ""
echo "OK: automated verification passed"
