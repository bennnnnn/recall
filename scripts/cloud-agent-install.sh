#!/usr/bin/env bash
#
# One-time install for the Recall Cloud Agent environment.
#
# Runs after the repository is checked out (and, with environment builds, once
# while baking the environment snapshot). It installs the system toolchain and
# project dependencies, then hands off to cloud-agent-start.sh to bring up
# PostgreSQL/Redis and apply migrations so the environment is immediately
# usable.
#
# Designed to be idempotent: re-running it is safe and fast (apt/uv/pnpm all
# no-op when already satisfied). It must not assume files that exist only on an
# unmerged branch beyond this repository's own tracked scripts.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

log() { echo "==> $*"; }

log "[1/5] System packages: PostgreSQL 16 + pgvector, Redis"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq \
  postgresql-16 \
  postgresql-16-pgvector \
  redis-server

log "[2/5] uv (Python package/venv manager)"
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

log "[3/5] Backend Python dependencies (apps/api)"
(cd "$ROOT/apps/api" && uv sync --all-groups --frozen)

log "[4/5] JavaScript dependencies (apps/web, apps/mobile)"
corepack enable
(cd "$ROOT/apps/web" && corepack pnpm install --frozen-lockfile)
(cd "$ROOT/apps/mobile" && corepack pnpm install --frozen-lockfile)

log "[5/5] Start services, ensure dev config, and migrate the database"
bash "$ROOT/scripts/cloud-agent-start.sh"

log "Recall environment install complete."
