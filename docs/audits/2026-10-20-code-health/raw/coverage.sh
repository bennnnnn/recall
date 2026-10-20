#!/bin/bash
# Coverage of the critical paths, one targeted run at a time.
OUT=/home/user/recall/tmp/code-audit/raw/coverage
mkdir -p $OUT
PY=/home/user/recall-audit/apps/api/.venv/bin/python
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/recall_cleanup
export REDIS_URL=redis://127.0.0.1:6379/0
export LITELLM_LOCAL_MODEL_COST_MAP=True
cd /home/user/recall-audit/apps/api
DES="--deselect app/tests/core/test_sympy_executor.py --deselect app/tests/security/test_zz_audit_io_counts.py"
run() { local name=$1; shift; $PY -m pytest -q -p no:cacheprovider $DES --cov-report=term-missing "$@" > $OUT/$name.txt 2>&1; echo "$name rc=$? :: $(grep -E '^TOTAL' $OUT/$name.txt)" >> $OUT/summary.txt; }
: > $OUT/summary.txt
run quota   --cov=app.services.quota --cov=app.core.spend_counter app/tests/services app/tests/security app/tests/modules/chat app/tests/core
run auth    --cov=app.modules.account --cov=app.core.access_tokens --cov=app.core.deps --cov=app.core.user_cache app/tests/modules/account app/tests/security app/tests/core app/tests/test_routers.py
run memory  --cov=app.modules.memory app/tests/modules/memory app/tests/security
run billing --cov=app.modules.billing --cov=app.gateways.revenuecat_gateway app/tests/modules/billing app/tests/security app/tests/background app/tests/gateways
run stream  --cov=app.modules.chat app/tests/modules/chat app/tests/security
echo DONE >> $OUT/summary.txt
