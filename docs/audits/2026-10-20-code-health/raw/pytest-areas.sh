#!/bin/bash
# One pytest area at a time, with the 30 slowest tests per area.
OUT=/home/user/recall/tmp/code-audit/raw/pytest
mkdir -p $OUT
PY=/home/user/recall-audit/apps/api/.venv/bin/python
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/recall_cleanup
export REDIS_URL=redis://127.0.0.1:6379/0
export LITELLM_LOCAL_MODEL_COST_MAP=True
cd /home/user/recall-audit/apps/api
: > $OUT/summary.txt
areas="app/tests/architecture app/tests/core app/tests/gateways app/tests/repositories app/tests/security app/tests/background app/tests/services app/tests/behavior"
for m in app/tests/modules/*/; do areas="$areas ${m%/}"; done
# top-level test files as one area
top=$(ls app/tests/test_*.py | tr '\n' ' ')
run() { local name=$1; shift; local s=$(date +%s); $PY -m pytest "$@" -q -p no:cacheprovider --durations=30 --deselect app/tests/core/test_sympy_executor.py --deselect app/tests/security/test_zz_audit_io_counts.py > "$OUT/$name.txt" 2>&1; local rc=$?; echo "$name rc=$rc secs=$(( $(date +%s) - s )) :: $(tail -1 "$OUT/$name.txt")" >> $OUT/summary.txt; }
for a in $areas; do run "$(echo $a | sed 's#app/tests/##; s#/#_#g')" "$a"; done
run toplevel $top
echo DONE >> $OUT/summary.txt
