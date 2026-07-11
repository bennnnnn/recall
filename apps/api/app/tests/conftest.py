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
