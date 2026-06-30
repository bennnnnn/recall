#!/usr/bin/env bash
#
# One-command local gate — mirrors CI exactly so "is it green?" is a single run.
# API order matches .github/workflows/api-ci.yml: ruff -> format -> mypy -> pytest.
# Skips a side cleanly if its toolchain isn't installed.
#
# Usage: ./scripts/check.sh            (also: ./scripts/dev.sh check)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0

echo "==> API: ruff check + format + mypy + pytest (coverage >= 80%)"
if command -v uv >/dev/null 2>&1; then
  (
    cd "$ROOT/apps/api" &&
      uv run ruff check . &&
      uv run ruff format --check . &&
      uv run mypy &&
      uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
  ) || fail=1
else
  echo "    WARN: uv not found - skipping API checks"
fi

echo "==> Mobile: typecheck + lint"
if command -v pnpm >/dev/null 2>&1; then
  (cd "$ROOT/apps/mobile" && pnpm typecheck && pnpm lint) || fail=1
else
  echo "    WARN: pnpm not found - skipping mobile checks"
fi

if [ "$fail" -ne 0 ]; then
  echo "FAIL: gate is red - fix the above before committing"
  exit 1
fi
echo "OK: gate is green"
