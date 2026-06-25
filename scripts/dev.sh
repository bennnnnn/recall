#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

kill_metro() {
  "$ROOT/scripts/kill-metro.sh" || true
}

case "${1:-}" in
  infra)
    echo "Optional: starts local Postgres + Redis via Docker."
    docker compose -f "$ROOT/docker-compose.yml" up -d
    ;;
  api)
    cd "$ROOT/apps/api"
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ;;
  mobile)
    kill_metro
    cd "$ROOT/apps/mobile"
    echo "LAN mode — phone and Mac must be on the same Wi‑Fi."
    echo "Unplug USB or authorize USB debugging if Android is connected."
    pnpm exec expo start --lan --clear
    ;;
  mobile-tunnel)
    kill_metro
    cd "$ROOT/apps/mobile"
    echo "Tunnel mode — scan QR in Expo Go (Wi‑Fi or cellular on phone)."
    echo "Tip: UNPLUG USB cable if adb reverse errors appear."
    adb kill-server 2>/dev/null || true
    pnpm exec expo start --tunnel --clear
    ;;
  kill-metro)
    kill_metro
    ;;
  migrate)
    cd "$ROOT/apps/api"
    uv run alembic upgrade head
    ;;
  test-api)
    cd "$ROOT/apps/api"
    uv run pytest
    ;;
  setup)
    cp -n "$ROOT/apps/api/.env.example" "$ROOT/apps/api/.env" 2>/dev/null || true
    cp -n "$ROOT/apps/mobile/.env.example" "$ROOT/apps/mobile/.env" 2>/dev/null || true
    cd "$ROOT/apps/api" && uv sync
    cd "$ROOT/apps/mobile" && pnpm install
    echo ""
    echo "Setup complete (no Docker)."
    echo ""
    echo "Next:"
    echo "  1. Add Neon + Upstash URLs to apps/api/.env"
    echo "  2. ./scripts/dev.sh migrate"
    echo "  3. ./scripts/dev.sh api   OR   ./scripts/dev.sh mobile"
    echo ""
    echo "Optional local DB: ./scripts/dev.sh infra  (requires Docker)"
    ;;
  *)
    echo "Usage: scripts/dev.sh {setup|migrate|api|mobile|mobile-tunnel|kill-metro|test-api|infra}"
    echo ""
    echo "  setup          Install deps, copy .env (no Docker)"
    echo "  migrate        Apply DB migrations (needs DATABASE_URL in .env)"
    echo "  api            Run FastAPI on :8000"
    echo "  mobile         Run Expo (LAN — same Wi‑Fi, unplug USB if adb errors)"
    echo "  mobile-tunnel  Run Expo (tunnel — unplug USB, scan QR in Expo Go)"
    echo "  kill-metro     Stop stale Metro servers on ports 8081–8090"
    echo "  infra          Optional: Docker Postgres + Redis"
    exit 1
    ;;
esac
