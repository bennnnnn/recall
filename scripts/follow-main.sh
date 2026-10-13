#!/usr/bin/env bash
# Keep this checkout on origin/main while the dev servers run, so a merged
# pull request reaches the running app without anyone pulling by hand.
#
# The API (uvicorn --reload) and Metro (Fast Refresh) reload changed files on
# their own; this only fast-forwards main, then installs dependencies and runs
# migrations when a pull changed them.
#
# It never touches work: it pulls only on main with no local changes, and
# only as a fast-forward. Otherwise it says why once and waits.
#
#   follow-main.sh                 check every FOLLOW_MAIN_INTERVAL seconds (60)
#   follow-main.sh --once          check once and exit
#   follow-main.sh --once --switch also leave a branch already merged into main
#
# Written for the bash 3.2 that macOS ships.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL="${FOLLOW_MAIN_INTERVAL:-60}"
ONCE=0
SWITCH=0
for arg in "$@"; do
  case "$arg" in
    --once) ONCE=1 ;;
    --switch) SWITCH=1 ;;
    *) echo "usage: follow-main.sh [--once] [--switch]" >&2; exit 2 ;;
  esac
done

cd "$ROOT" || exit 1

say() { printf '\033[36m[follow-main]\033[0m %s\n' "$*"; }

LAST_NOTICE=""
notice_once() {
  if [[ "$1" != "$LAST_NOTICE" ]]; then
    say "$1"
    LAST_NOTICE="$1"
  fi
}

after_pull() {
  local before="$1" changed
  changed="$(git diff --name-only "$before" HEAD)"
  say "Updated to $(git log -1 --format='%h %s')"
  if grep -qE '^apps/api/(pyproject\.toml|uv\.lock)$' <<<"$changed"; then
    say "API dependencies changed: uv sync"
    (cd apps/api && uv sync -q)
  fi
  if grep -q '^apps/api/alembic/versions/' <<<"$changed"; then
    say "New database migration: alembic upgrade head"
    (cd apps/api && uv run alembic upgrade head)
  fi
  if grep -qE '^apps/mobile/(package\.json|pnpm-lock\.yaml)$' <<<"$changed"; then
    say "Mobile dependencies changed: pnpm install"
    (cd apps/mobile && pnpm install --silent)
    say "Restart the app (Ctrl+C, then ./scripts/dev.sh up) to load them."
  fi
  if grep -qE '^apps/mobile/(app\.config\.ts|plugins/)' <<<"$changed"; then
    say "The app's native config changed: restart the app to load it."
  fi
}

sync_once() {
  local branch behind before
  if ! git fetch -q origin main 2>/dev/null; then
    notice_once "Could not reach GitHub; will try again."
    return
  fi
  branch="$(git symbolic-ref --short -q HEAD || true)"
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    behind="$(git rev-list --count HEAD..origin/main)"
    [[ "$behind" -gt 0 ]] && notice_once "main has new commits; not pulling over your local changes."
    return
  fi
  if [[ "$branch" != "main" ]]; then
    # A branch already merged into main holds nothing main lacks.
    if [[ "$SWITCH" -eq 1 ]] && git merge-base --is-ancestor HEAD origin/main; then
      say "Leaving ${branch:-a detached HEAD} (already in main) for main."
      git switch -q main || return
    else
      behind="$(git rev-list --count main..origin/main 2>/dev/null || echo 0)"
      [[ "$behind" -gt 0 ]] && notice_once "main has new commits; you are on ${branch:-a detached HEAD}, so not pulling."
      return
    fi
  fi
  behind="$(git rev-list --count HEAD..origin/main)"
  [[ "$behind" -eq 0 ]] && return
  before="$(git rev-parse HEAD)"
  if git merge --ff-only -q origin/main; then
    LAST_NOTICE=""
    after_pull "$before"
  else
    notice_once "Could not fast-forward main (it has commits origin/main lacks)."
  fi
}

sync_once
[[ "$ONCE" -eq 1 ]] && exit 0
while sleep "$INTERVAL"; do
  sync_once
done
