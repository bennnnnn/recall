"""An answer photo found once is reused for the same lookup, and each lookup says where its
time went.

2026-11-09: "where is Ethiopia" showed "finding a photo" and then nothing; the lookup ran
past the reply's wait and nothing logged which step had stalled. The same words looked up
again searched Tavily and fetched the photo again.
"""

import json
import logging
from contextlib import ExitStack
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.background_tasks import drain_background_tasks
from app.core.config import Settings
from app.gateways.image_search_gateway import ImageSearchHit
from app.gateways.storage_gateway import LocalStorageGateway
from app.modules.attachments import lifecycle
from app.modules.images import photo_cache
from app.modules.images.search import photos_for_answer
from app.tests.fakes import make_user

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32
_HIT = ImageSearchHit(
    image_url="https://upload.wikimedia.org/ethiopia.png",
    description="Ethiopia map",
    source_url="https://en.wikipedia.org/wiki/Ethiopia",
    source_title="Ethiopia",
)
SETTINGS = Settings(image_search_enabled=True, attachments_enabled=True)
# A fixed "now" for the record checks: a time, not a duration measured.
NOW = 1_800_000_000.0


def _lookup(gateway, redis) -> dict:
    """A lookup over real local storage and Redis; the web and the charges are mocks."""
    response = MagicMock(status_code=200, headers={"content-type": "image/png"}, content=PNG_BYTES)
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    search = "app.modules.images.search"
    return {
        "storage": patch(f"{search}.get_storage_gateway", return_value=gateway),
        "redis": patch(f"{search}.get_redis_client", return_value=redis),
        "spend_cap": patch(
            f"{search}.quota_service.global_spend_exceeded", AsyncMock(return_value=False)
        ),
        "reserve": patch(f"{search}.counters.reserve", AsyncMock(return_value=date(2026, 11, 9))),
        "search": patch(
            f"{search}.image_search_gateway.search_images", AsyncMock(return_value=[_HIT])
        ),
        "client": patch("app.gateways.safe_fetch.fetch_client", return_value=client),
        "fetch": patch(f"{search}.safe_fetch.fetch_safely", AsyncMock(return_value=response)),
        "rows": patch(f"{search}.attachments_service.add_server_images", AsyncMock()),
        "spend": patch(f"{search}.quota_service.record_global_spend", AsyncMock()),
        "refund": patch(f"{search}.counters.refund", AsyncMock()),
    }


def _entered(stack: ExitStack, patches: dict) -> dict:
    return {name: stack.enter_context(patcher) for name, patcher in patches.items()}


def _stored_key(rows: AsyncMock) -> str:
    assert rows.await_args is not None
    return str(rows.await_args.kwargs["images"][0].storage_key)


@pytest.fixture
def gateway(tmp_path) -> LocalStorageGateway:
    return LocalStorageGateway(tmp_path)


async def test_a_second_lookup_of_the_same_words_reuses_the_photo(gateway, fake_redis):
    first_user, second_user = make_user(), make_user()
    with ExitStack() as stack:
        mocks = _entered(stack, _lookup(gateway, fake_redis))
        first = await photos_for_answer(SETTINGS, user=first_user, query="Ethiopia location map")
        await drain_background_tasks()
        first_key = _stored_key(mocks["rows"])
        for mock in mocks.values():
            if isinstance(mock, AsyncMock):
                mock.reset_mock()
        second = await photos_for_answer(
            SETTINGS, user=second_user, query="  ethiopia   LOCATION map"
        )

    assert len(second) == 1 and second != first
    # No search, no fetch from a third-party host, and nothing charged.
    mocks["search"].assert_not_awaited()
    mocks["fetch"].assert_not_awaited()
    for charge in ("spend_cap", "reserve", "spend"):
        mocks[charge].assert_not_awaited()
    # The second user's own attachment, under their own prefix, with the same bytes.
    added = mocks["rows"].await_args.kwargs
    assert added["user_id"] == second_user.id and added["message_id"] is None
    assert added["label"] == "ethiopia LOCATION map"
    second_key = _stored_key(mocks["rows"])
    assert second_key.startswith(f"{second_user.id}/") and second_key != first_key
    assert await gateway.read_bytes(second_key) == PNG_BYTES


async def test_the_cache_keeps_no_words_and_no_user(gateway, fake_redis):
    with ExitStack() as stack:
        _entered(stack, _lookup(gateway, fake_redis))
        await photos_for_answer(SETTINGS, user=make_user(), query="Ethiopia location map")
        await drain_background_tasks()
    keys = await fake_redis.keys("answer_photo_cache:*")
    record_keys = [key for key in keys if key != "answer_photo_cache:stored"]
    assert len(record_keys) == 1
    stored = await fake_redis.get(record_keys[0])
    assert "ethiopia" not in (record_keys[0] + stored).casefold()
    record = json.loads(stored)
    assert record["storage_key"].startswith(photo_cache.SHARED_PREFIX)
    assert set(record) == {"storage_key", "content_type", "size_bytes", "stored_at"}
    # Kept about 30 days.
    assert 29 * 24 * 60 * 60 < await fake_redis.ttl(record_keys[0]) <= 30 * 24 * 60 * 60


async def test_a_photo_kept_past_its_age_is_looked_up_again(gateway, fake_redis):
    record_key = f"answer_photo_cache:{photo_cache.lookup_digest('capybara')}"
    with ExitStack() as stack:
        mocks = _entered(stack, _lookup(gateway, fake_redis))
        await photos_for_answer(SETTINGS, user=make_user(), query="capybara")
        await drain_background_tasks()
        mocks["search"].reset_mock()
        # Stored 31 days ago: the record's own time says so, whatever Redis still holds.
        record = json.loads(await fake_redis.get(record_key))
        record["stored_at"] -= 31 * 24 * 60 * 60
        await fake_redis.set(record_key, json.dumps(record))
        await photos_for_answer(SETTINGS, user=make_user(), query="capybara")
    mocks["search"].assert_awaited_once()


async def test_the_sweep_deletes_aged_shared_copies_only(gateway, fake_redis):
    with ExitStack() as stack:
        _entered(stack, _lookup(gateway, fake_redis))
        await photos_for_answer(SETTINGS, user=make_user(), query="capybara")
        await drain_background_tasks()
    shared = f"{photo_cache.SHARED_PREFIX}{photo_cache.lookup_digest('capybara')}"
    assert await gateway.read_bytes(shared) == PNG_BYTES

    assert await photo_cache.sweep_expired(SETTINGS, gateway, fake_redis) == 0
    assert await gateway.read_bytes(shared) == PNG_BYTES
    record_key = f"answer_photo_cache:{photo_cache.lookup_digest('capybara')}"
    month_on = json.loads(await fake_redis.get(record_key))["stored_at"] + 31 * 24 * 60 * 60
    assert await photo_cache.sweep_expired(SETTINGS, gateway, fake_redis, now=month_on) == 1
    assert await gateway.read_bytes(shared) is None
    assert await fake_redis.zcard("answer_photo_cache:stored") == 0


async def test_a_shared_copy_gone_from_storage_is_looked_up_again(gateway, fake_redis):
    with ExitStack() as stack:
        mocks = _entered(stack, _lookup(gateway, fake_redis))
        await photos_for_answer(SETTINGS, user=make_user(), query="capybara")
        await drain_background_tasks()
        await gateway.delete_bytes(
            f"{photo_cache.SHARED_PREFIX}{photo_cache.lookup_digest('capybara')}"
        )
        mocks["search"].reset_mock()
        ids = await photos_for_answer(SETTINGS, user=make_user(), query="capybara")
    assert len(ids) == 1
    mocks["search"].assert_awaited_once()


async def test_deleting_an_account_removes_its_copy_and_leaves_the_shared_one(gateway, fake_redis):
    leaving = make_user()
    with ExitStack() as stack:
        mocks = _entered(stack, _lookup(gateway, fake_redis))
        await photos_for_answer(SETTINGS, user=make_user(), query="capybara")
        await drain_background_tasks()
        await photos_for_answer(SETTINGS, user=leaving, query="capybara")
        own_copy = _stored_key(mocks["rows"])
    assert own_copy.startswith(f"{leaving.id}/")

    with patch.object(lifecycle, "get_storage_gateway", return_value=gateway):
        await lifecycle.delete_storage_keys(SETTINGS, [own_copy])
        await lifecycle.sweep_user_storage(SETTINGS, leaving.id)

    assert await gateway.read_bytes(own_copy) is None
    shared = f"{photo_cache.SHARED_PREFIX}{photo_cache.lookup_digest('capybara')}"
    assert await gateway.read_bytes(shared) == PNG_BYTES


async def test_the_cache_is_off_at_zero_days(gateway, fake_redis):
    settings = Settings(image_search_enabled=True, answer_photo_cache_days=0)
    with ExitStack() as stack:
        mocks = _entered(stack, _lookup(gateway, fake_redis))
        for _ in range(2):
            await photos_for_answer(settings, user=make_user(), query="capybara")
            await drain_background_tasks()
    assert mocks["search"].await_count == 2
    assert await fake_redis.keys("answer_photo_cache:*") == []


async def test_each_lookup_logs_the_time_of_every_step(gateway, fake_redis, caplog):
    caplog.set_level(logging.INFO, logger="app.modules.images.lookup_clock")
    with ExitStack() as stack:
        _entered(stack, _lookup(gateway, fake_redis))
        await photos_for_answer(SETTINGS, user=make_user(), query="Ethiopia location map")
        await drain_background_tasks()
        await photos_for_answer(SETTINGS, user=make_user(), query="Ethiopia location map")

    found, cached = [r.getMessage() for r in caplog.records if "answer_photo_lookup" in r.message]
    assert found.startswith("answer_photo_lookup outcome=found cache_ms=")
    for step in ("checks_ms=", "search_ms=", "fetch_ms=", "store_ms=", "row_ms=", "total_ms="):
        assert step in found
    assert "host=upload.wikimedia.org" in found
    assert cached.startswith("answer_photo_lookup outcome=cached cache_ms=")
    assert "store_ms=" in cached and "row_ms=" in cached and "search_ms" not in cached
    # The words looked up are never in the line.
    assert "ethiopia" not in (found + cached).casefold()


async def test_a_spent_lookup_allowance_is_logged_as_the_limit(gateway, fake_redis, caplog):
    caplog.set_level(logging.INFO, logger="app.modules.images.lookup_clock")
    with ExitStack() as stack:
        mocks = _entered(stack, _lookup(gateway, fake_redis))
        mocks["reserve"].return_value = None
        assert await photos_for_answer(SETTINGS, user=make_user(), query="capybara") == []
    (line,) = [r.getMessage() for r in caplog.records if "answer_photo_lookup" in r.message]
    assert "outcome=limit" in line and "checks_ms=" in line


@pytest.mark.parametrize(
    "raw",
    [None, "not json", json.dumps({"storage_key": "someone/else"}), b"{}", 42],
)
def test_a_record_this_module_did_not_write_is_no_hit(raw):
    assert photo_cache._parsed(raw, max_age=60, now=NOW) is None


def test_a_users_key_is_never_read_as_a_shared_copy():
    record = {"content_type": "image/png", "size_bytes": 3, "stored_at": NOW}
    shared = json.dumps({**record, "storage_key": f"{photo_cache.SHARED_PREFIX}abc"})
    users = json.dumps({**record, "storage_key": f"{uuid4()}/{uuid4()}"})
    assert photo_cache._parsed(shared, max_age=60, now=NOW) is not None
    assert photo_cache._parsed(users, max_age=60, now=NOW) is None
