#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

kill_metro() {
  "$ROOT/scripts/kill-metro.sh" || true
}

kill_all_dev() {
  echo "Stopping API, Metro, and Expo…"
  lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null || true
  pkill -9 -f "uvicorn app.main" 2>/dev/null || true
  kill_metro
  pkill -9 -f "expo start" 2>/dev/null || true
  pkill -9 -f "expo/bin/cli" 2>/dev/null || true
  xcrun simctl terminate booted host.exp.Exponent 2>/dev/null || true
  echo "All dev servers stopped."
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
  mobile-sim)
    kill_metro
    "$ROOT/scripts/set-sim-ip.sh"
    cd "$ROOT/apps/mobile"
    echo "iOS Simulator — Expo Go on virtual device (API at 127.0.0.1:8000)."
    pnpm exec expo start --lan --clear --go --ios
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
  kill-all)
    kill_all_dev
    ;;
  migrate)
    cd "$ROOT/apps/api"
    uv run alembic upgrade head
    ;;
  test-api)
    cd "$ROOT/apps/api"
    uv run pytest
    ;;
  check)
    "$ROOT/scripts/check.sh"
    ;;
  qa-smoke)
    shift
    "$ROOT/scripts/qa-smoke.sh" "$@"
    ;;
  verify-production)
    shift
    "$ROOT/scripts/verify-production.sh" "$@"
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
    echo "Usage: scripts/dev.sh {setup|migrate|api|mobile|mobile-sim|mobile-tunnel|kill-metro|kill-all|test-api|check|qa-smoke|verify-production|infra}"
    echo ""
    echo "  setup          Install deps, copy .env (no Docker)"
    echo "  migrate        Apply DB migrations (needs DATABASE_URL in .env)"
    echo "  api            Run FastAPI on :8000"
    echo "  check          Run the full local gate (API ruff+format+mypy+pytest, mobile typecheck+lint)"
    echo "  qa-smoke       Backend smoke checks (add --live when API is running)"
    echo "  verify-production  Production readiness report (add --live for deployed API)"
    echo "  mobile         Run Expo (LAN — same Wi‑Fi, unplug USB if adb errors)"
    echo "  mobile-sim     Run Expo Go on iOS Simulator (localhost)"
    echo "  mobile-tunnel  Run Expo (tunnel — unplug USB, scan QR in Expo Go)"
    echo "  kill-metro     Stop stale Metro servers on ports 8081–8090"
    echo "  kill-all       Stop API (:8000), Metro, Expo, and Expo Go on simulator"
    echo "  infra          Optional: Docker Postgres + Redis"
    exit 1
    ;;
esac
