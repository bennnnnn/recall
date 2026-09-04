"""Nonessential title work must not prevent reopening a saved conversation."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services import chats


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_step", ["claim", "enqueue"])
async def test_saved_messages_remain_readable_when_title_backfill_fails(failure_step):
    redis = AsyncMock()
    enqueue = AsyncMock()
    failing = redis.set if failure_step == "claim" else enqueue
    failing.side_effect = RuntimeError("queue unavailable")
    rows = [
        SimpleNamespace(
            id=uuid4(),
            role=role,
            content=content,
            model="free-chat",
            created_at=datetime.now(UTC),
        )
        for role, content in [("user", "Hello"), ("assistant", "Hi there")]
    ]
    with (
        patch("app.services.chats.get_chat", AsyncMock(return_value=SimpleNamespace(title=None))),
        patch("app.services.chats.finalize_registry.wait_for_inflight_stream", AsyncMock()),
        patch("app.services.chats.finalize_registry.wait_for_pending_finalize", AsyncMock()),
        patch("app.services.chats.messages_repo.list_page", AsyncMock(return_value=(rows, False))),
        patch("app.services.chats.jobs.enqueue", enqueue),
    ):
        page = await chats.list_messages_page(
            AsyncMock(), redis, SimpleNamespace(id=uuid4()), uuid4()
        )
    assert [message.content for message in page.messages] == ["Hello", "Hi there"]
    assert not page.has_more
