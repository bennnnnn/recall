#!/bin/bash
# Analysis tools, one after another. Waits for baseline.sh to finish first.
OUT=/home/user/recall/tmp/code-audit/raw
W=/home/user/recall-audit
PY=/home/user/recall/apps/api/.venv/bin/python
while ! grep -q DONE "$OUT/baseline-summary.txt" 2>/dev/null; do sleep 10; done
t() { local name=$1; shift; local s=$(date +%s); timeout 900 "$@" > "$OUT/$name.txt" 2>&1; echo "$name exit=$? secs=$(( $(date +%s) - s ))" >> "$OUT/tools-summary.txt"; }
: > "$OUT/tools-summary.txt"
cd $W/apps/api
t pylint-dup uvx pylint --disable=all --enable=duplicate-code --min-similarity-lines=8 app
t vulture uvx vulture app --min-confidence 80
t radon-cc uvx radon cc app -s -n C
t radon-mi uvx radon mi app -s
VIRTUAL_ENV=/home/user/recall/apps/api/.venv t deptry uvx deptry .
{ uvx pylint --version; uvx vulture --version; uvx radon --version; uvx deptry --version; } > "$OUT/versions-tools.txt" 2>&1
cd $W
t jscpd npx --yes jscpd@4 --min-lines 10 --reporters console,json --output "$OUT/jscpd" --ignore "**/tests/**,**/__tests__/**,**/vendor/**,**/*.generated.*,**/node_modules/**" apps/api/app apps/mobile/app apps/mobile/components apps/mobile/features apps/mobile/lib apps/mobile/ui apps/mobile/hooks apps/mobile/contexts
cd $W/apps/mobile
t knip npx --yes knip --no-progress
t depcheck npx --yes depcheck --json
{ npx --yes jscpd@4 --version; npx --yes knip --version; npx --yes depcheck --version; } >> "$OUT/versions-tools.txt" 2>&1
echo DONE >> "$OUT/tools-summary.txt"
