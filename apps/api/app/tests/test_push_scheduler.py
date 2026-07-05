"""Push scheduler lock tests."""

from app.background import push_scheduler


def test_push_lock_ttl_exceeds_interval():
    assert push_scheduler.LOCK_TTL_SECONDS > push_scheduler.INTERVAL_SECONDS
