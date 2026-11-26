"""Each test reads ``/health/ready`` afresh: the route keeps its database answer a few
seconds (``READY_CHECK``), which would carry one test's database into the next."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest

from app.routers import health


@pytest.fixture(autouse=True)
def fresh_ready_check() -> Iterator[None]:
    check = health.DependencyCheck(
        health.database_answers, ttl_seconds=health.READY_CHECK_TTL_SECONDS
    )
    with patch.object(health, "READY_CHECK", check):
        yield
