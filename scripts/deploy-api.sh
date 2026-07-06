#!/usr/bin/env bash
# Deploy Recall API to Fly.io (recall-api). Requires flyctl auth and secrets set.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FLY_APP="${FLY_APP:-recall-api}"

if ! command -v flyctl >/dev/null 2>&1 && ! command -v fly >/dev/null 2>&1; then
  echo "flyctl not found. Install: https://fly.io/docs/hands-on/install-flyctl/" >&2
  exit 1
fi

FLY="${FLYCTL:-flyctl}"
command -v "$FLY" >/dev/null 2>&1 || FLY=fly

if [[ -f "$ROOT/apps/api/.env.production" ]]; then
  echo "==> Validating apps/api/.env.production"
  "$ROOT/scripts/validate-prod-env.sh"
else
  echo "WARN: apps/api/.env.production not found — assuming Fly secrets already set"
fi

echo "==> Deploying $FLY_APP (remote build)"
cd "$ROOT"
"$FLY" deploy --app "$FLY_APP" --remote-only

HOST="$("$FLY" info --app "$FLY_APP" --json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d.get('Hostname') or d.get('hostname') or '')
" 2>/dev/null || true)"

if [[ -n "$HOST" ]]; then
  echo
  echo "==> Smoke checks"
  curl -sf "https://${HOST}/health/ready" && echo "  OK  /health/ready"
  curl -sf "https://${HOST}/legal/privacy" | head -c 80 && echo " ... OK  /legal/privacy"
  echo
  echo "API URL: https://${HOST}"
  echo "Set EXPO_PUBLIC_API_URL=https://${HOST} in EAS secrets before mobile production build."
else
  echo "Deploy finished. Run: flyctl info --app $FLY_APP"
fi
