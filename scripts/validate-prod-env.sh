#!/usr/bin/env bash
# Validate apps/api/.env.production against production boot rules (no deploy).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT/apps/api/.env.production}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  echo "Copy apps/api/.env.production.example → apps/api/.env.production and fill values."
  exit 1
fi

echo "Validating $ENV_FILE ..."
cd "$ROOT/apps/api"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
export ENVIRONMENT=production

uv run python - <<'PY'
from app.core.config import Settings, validate_production_settings

settings = Settings()
validate_production_settings(settings)
print("OK: production configuration passes validate_production_settings()")
PY
