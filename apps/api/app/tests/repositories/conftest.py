"""Fixtures for real-Postgres repository tests (the `*_db.py` files in this
directory), as opposed to the mocked `AsyncMock(spec=AsyncSession)` unit
tests in the sibling `test_*.py` files.

The mocked tests only prove "did the repository call `.execute()`/`.commit()`
at all" — the mock returns the same canned result no matter what SQL was
built, so they can't catch a broken `WHERE user_id ==` filter, a wrong join,
a wrong column, or incorrect ordering/limit. The `db_session` fixture here
gives the `*_db.py` tests a real `AsyncSession` bound to a real Postgres
connection so the actual compiled SQL runs.

Requires a reachable Postgres at `DATABASE_URL` with migrations applied.
CI (`.github/workflows/api-ci.yml`) provisions a `pgvector/pgvector:pg16`
service and runs `alembic upgrade head` before pytest. There is deliberately
no skip-if-unreachable guard: a missing/unmigrated database should fail
these tests loudly, not silently skip the exact regression net they exist
to provide.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import engine


@pytest.fixture
async def db_session():
    """Real `AsyncSession` wrapped in an outer transaction + SAVEPOINT that
    is always rolled back, so tests need no manual cleanup and can't leak
    state between tests or pollute the shared database.

    This is SQLAlchemy's documented recipe for joining a `Session` into an
    external transaction for test suites: open a connection, begin an outer
    transaction on it, then bind the `AsyncSession` to that same connection
    with `join_transaction_mode="create_savepoint"`. With that mode, every
    `session.commit()` performed by repository code under test only
    releases (and SQLAlchemy immediately re-creates) a SAVEPOINT — it never
    touches the outer transaction. Rolling back the outer transaction at
    teardown discards everything unconditionally, including anything that
    was "committed" from the repository code's point of view.
    """
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
    # asyncpg connections are bound to the event loop that opened them, and
    # pytest-asyncio (asyncio_default_fixture_loop_scope = "function", see
    # pyproject.toml) gives every test function its own event loop. Without
    # this, a connection born on test A's loop could get checked back out
    # to test B on a different loop and blow up with "Future attached to a
    # different loop". Disposing the pool after every test guarantees the
    # next test's first checkout always dials a fresh connection on its own
    # (current) loop.
    await engine.dispose()
