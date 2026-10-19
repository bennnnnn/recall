"""A user change the caller has not committed never reaches the per-process user cache.

``users.update(commit=False)`` used to cache the new values at flush. When the
caller's commit then failed and rolled back, this process served the unsaved
profile to every request for up to the cache TTL.
"""

from uuid import uuid4

import pytest

from app.core import user_cache
from app.models.orm import User
from app.repositories import users


async def _user(session) -> User:
    return await users.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Before",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


@pytest.fixture(autouse=True)
def _empty_cache():
    user_cache.clear()
    yield
    user_cache.clear()


async def test_an_uncommitted_change_is_not_cached_until_the_commit(db_session):
    user = await _user(db_session)

    await users.update(db_session, user, commit=False, name="After")
    assert user_cache.cached_user(user.id) is None

    await db_session.commit()
    cached = user_cache.cached_user(user.id)
    assert cached is not None
    assert cached.name == "After"


async def test_a_rolled_back_change_is_never_served_from_the_cache(db_session):
    user = await _user(db_session)
    user_id = user.id  # the rollback expires the row; reading it again would load it
    user_cache.remember_user(user)

    await users.update(db_session, user, commit=False, name="Unsaved")
    await db_session.rollback()

    assert user_cache.cached_user(user_id) is None
    # A later commit on the same session does not bring the unsaved values back.
    await db_session.commit()
    assert user_cache.cached_user(user_id) is None


async def test_a_committed_update_is_cached_at_once(db_session):
    user = await _user(db_session)

    await users.update(db_session, user, name="Saved")

    cached = user_cache.cached_user(user.id)
    assert cached is not None
    assert cached.name == "Saved"
