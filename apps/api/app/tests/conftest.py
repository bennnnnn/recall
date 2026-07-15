import os
from unittest.mock import patch

import fakeredis.aioredis
import pytest

# Match local `.env.example` — Settings.environment defaults to production
# (fail-closed). Tests that construct Settings() without an env file need this.
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture
async def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture(autouse=True)
def _isolate_rest_rate_limiter():
    """Give the global REST rate-limit middleware a fresh in-memory Redis per
    test so counters don't accumulate across the suite against the real Redis
    (which produced spurious 429s and order-dependent failures locally).

    Tests that exercise the limiter directly patch `allow_request`/`get_redis_client`
    inside their own `with patch(...)` blocks, which override this for their
    duration. The middleware otherwise hits the fake client, whose counts start
    at zero every test.
    """
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.core.rest_rate_limit.get_redis_client", return_value=client):
        yield


@pytest.fixture(autouse=True)
def _reset_sympy_executor():
    """Drop the bounded SymPy executor between tests so each test gets a fresh
    pool (forking after any monkeypatch is applied, so the worker inherits the
    patched module). Without this, a pool created by an earlier test would be
    reused and would NOT see patches applied in the current test."""
    from app.services.sympy_executor import reset_sympy_executor

    reset_sympy_executor()
    yield
    reset_sympy_executor()


@pytest.fixture
def thread_sympy_executor():
    """Swap the production ProcessPoolSympyExecutor for an in-process
    thread-based one. Needed for tests that monkeypatch module-level SymPy
    functions with local closures (closures aren't picklable across a
    subprocess boundary) or that spy on in-process state (a subprocess can't
    write back to the test's memory). The production executor's hard-kill
    behavior is exercised in test_sympy_executor.py."""
    from app.services.sympy_executor import (
        ThreadSympyExecutor,
        reset_sympy_executor,
        set_sympy_executor,
    )

    set_sympy_executor(ThreadSympyExecutor(max_workers=1))
    yield
    reset_sympy_executor()
