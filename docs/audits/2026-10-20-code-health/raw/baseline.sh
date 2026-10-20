#!/bin/bash
# Baseline checks, run one after another (never in parallel).
OUT=/home/user/recall/tmp/code-audit/raw
PY=/home/user/recall/apps/api/.venv/bin/python
W=/home/user/recall-audit
t() { local name=$1; shift; local s=$(date +%s); "$@" > "$OUT/$name.txt" 2>&1; echo "$name exit=$? secs=$(( $(date +%s) - s ))" >> "$OUT/baseline-summary.txt"; }
: > "$OUT/baseline-summary.txt"
cd $W/apps/api
{ $PY -m ruff --version; $PY -m mypy --version; } > "$OUT/versions-api.txt" 2>&1
t ruff $PY -m ruff check app
t ruff-format $PY -m ruff format --check app
t mypy $PY -m mypy app
cd $W
t file-sizes python3 scripts/check_file_sizes.py api mobile
cd $W/apps/mobile
{ npx tsc --version; npx eslint --version; node --version; pnpm --version; } > "$OUT/versions-mobile.txt" 2>&1
t typecheck pnpm typecheck
t lint pnpm lint
echo DONE >> "$OUT/baseline-summary.txt"
