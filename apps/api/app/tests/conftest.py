import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest

# Match local `.env.example` — Settings.environment defaults to production
# (fail-closed). Tests that construct Settings() without an env file need this.
os.environ.setdefault("ENVIRONMENT", "development")

# LiteLLM's import runs load_dotenv() in its default DEV mode, copying a developer's
# apps/api/.env into os.environ, where it outranks Settings defaults. Tests then pass
# in CI and fail locally (a lower DAILY_TOKEN_LIMIT, say). Any other mode skips it.
os.environ.setdefault("LITELLM_MODE", "PRODUCTION")

# CI has no provider key, so mock mode (``should_mock_llm``: enabled and no key) is what the
# suite is written against. A developer's apps/api/.env key would turn it off and send those
# tests to the real provider. A key exported in the shell still wins.
os.environ.setdefault("OPENROUTER_API_KEY", "")

# A maths decline that would hide a programming error (an AttributeError, NameError or our
# own TypeError; see app/modules/math/solve/declines.py) raises under pytest. A value already in
# the environment wins: RECALL_STRICT_DECLINES=0 runs the suite with production's declines.
_STRICT_DECLINES_ASKED = "RECALL_STRICT_DECLINES" in os.environ
os.environ.setdefault("RECALL_STRICT_DECLINES", "1")


@pytest.fixture
async def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def production_declines(monkeypatch):
    """Maths declines as production has them (silent), unless the run set RECALL_STRICT_DECLINES."""
    if not _STRICT_DECLINES_ASKED:
        monkeypatch.setenv("RECALL_STRICT_DECLINES", "0")


@pytest.fixture
def quota_clock():
    """The UTC day the daily counters see, 2026-10-16 until a test sets ``.day``.

    A provider fake that sets ``quota_clock.day = quota_clock.next_day`` makes
    its request run past UTC midnight.
    """
    clock = SimpleNamespace(day=date(2026, 10, 16), next_day=date(2026, 10, 17))
    with patch("app.services.quota.counters.utc_today", side_effect=lambda: clock.day):
        yield clock


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
def _ai_data_consent_given():
    """Test users have agreed to what goes to outside AI services.

    The consent gate (``app/modules/account/consent.py``) refuses a chat turn,
    speech and a scan read for an account that has not; most tests build users
    without that column. A test that checks the refusal takes ``consent_enforced``.
    """
    given = patch("app.modules.account.consent.has_ai_data_consent", return_value=True)
    given.start()
    yield given
    given.stop()


@pytest.fixture
def consent_enforced(_ai_data_consent_given):
    """The real consent check, for tests of the refusal."""
    _ai_data_consent_given.stop()


@pytest.fixture(autouse=True)
def model_spend_redis():
    """The gateway spend meter's Redis: a fresh fake per test, never the real one.

    A test whose provider fake reports token usage would otherwise add to the
    real ``spend_musd`` counter. Tests read this fixture to see what was metered.
    """
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.gateways.llm_spend.get_redis_client", return_value=client):
        yield client


@pytest.fixture(autouse=True)
def structured_invalid_redis():
    """The invalid-structured-output counter's Redis: a fresh fake per test."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.gateways.structured_completion.get_redis_client", return_value=client):
        yield client


@pytest.fixture(autouse=True)
def _no_real_embedding_provider():
    """The embedding provider is never called from a test.

    ``embed_many`` sends batches before it falls back to ``embed_text``, so a
    test that patches only ``embed_text`` would otherwise send its first batch
    to the real provider. A failed batch takes the fallback; tests of the
    request itself patch ``aembedding`` over this.
    """
    refused = AsyncMock(side_effect=RuntimeError("no embedding provider in tests"))
    with patch("app.gateways.embedding_gateway.aembedding", refused):
        yield


@pytest.fixture(autouse=True)
def ocr_allowance_redis():
    """The OCR allowance and kept OCR text: a fresh fake per test, never the real one.

    Every index job reads it, so a test that indexes a file would otherwise reach
    the real Redis (and a client bound to an earlier test's event loop).
    """
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.modules.attachments.ocr_allowance.get_redis_client", return_value=client):
        yield client


@pytest.fixture(autouse=True)
def _reset_sympy_executor():
    """Use a fresh in-process math worker for ordinary unit tests.

    Production hard-kill behavior has dedicated ProcessPoolSympyExecutor
    tests. Spawning a new subprocess pool in every unrelated async test is
    both unnecessary and capable of exhausting macOS's semaphore table over
    a full suite. The thread worker also correctly observes monkeypatches;
    the production ``spawn`` context intentionally does not inherit them.
    """
    from app.core.sympy_executor import (
        ThreadSympyExecutor,
        reset_sympy_executor,
        set_sympy_executor,
    )

    set_sympy_executor(ThreadSympyExecutor(max_workers=1))
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
    from app.core.sympy_executor import (
        ThreadSympyExecutor,
        reset_sympy_executor,
        set_sympy_executor,
    )

    set_sympy_executor(ThreadSympyExecutor(max_workers=1))
    yield
    reset_sympy_executor()


@pytest.fixture
async def db_session():
    """Real Postgres session isolated by an outer transaction and savepoints.

    Product-module and repository tests share this fixture. A commit issued by
    code under test only releases a savepoint; the outer rollback always
    discards the test's data.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.db import engine

    # Connections are bound to the event loop that opened them. Forget any
    # pooled connection left by a TestClient/anyio loop before and after use.
    await engine.dispose(close=False)
    async with engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()
    await engine.dispose(close=False)
