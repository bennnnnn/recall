"""Finalize must not refund after a successful DB commit."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.post_turn import finalize_stream_turn_db
from app.services.chat.turn_prep import RegenerateBackup, StreamContext


class _FakeSessionCM:
    def __init__(self, session: AsyncMock):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_adjust_usage_failure_after_commit_does_not_refund():
    user_id = uuid4()
    chat_id = uuid4()
    redis = AsyncMock()
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    assistant = MagicMock()
    assistant.id = uuid4()

    ctx = StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hi"}],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=200,
        max_output_tokens=50,
        skip_memory_jobs=True,
        user=MagicMock(plan="free"),
    )

    refund = AsyncMock()
    adjust = AsyncMock(side_effect=RuntimeError("redis blip"))

    with (
        patch("app.services.chat.post_turn.SessionLocal", lambda: _FakeSessionCM(session)),
        patch(
            "app.services.chat.post_turn.messages_repo.create",
            AsyncMock(return_value=assistant),
        ),
        patch("app.services.chat.post_turn.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.post_turn.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.post_turn.quota_service.adjust_usage", adjust),
        patch("app.services.chat.post_turn.quota_service.refund_usage", refund),
        patch(
            "app.services.chat.post_turn.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch("app.services.chat.post_turn.get_settings", return_value=Settings()),
    ):
        await finalize_stream_turn_db(
            redis,
            ctx,
            "hello",
            {"input": 10, "output": 5},
            result={},
        )

    session.commit.assert_awaited()
    # H2: adjust_usage retries 3 times on failure before giving up.
    assert adjust.await_count == 3
    refund.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_persists_estimated_cost_usd():
    """Known model + usage → est_cost_usd written on the usage row."""
    user_id = uuid4()
    chat_id = uuid4()
    redis = AsyncMock()
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    assistant = MagicMock()
    assistant.id = uuid4()

    ctx = StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hi"}],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=200,
        max_output_tokens=50,
        skip_memory_jobs=True,
        user=MagicMock(plan="free"),
    )

    add_tokens = AsyncMock()
    with (
        patch("app.services.chat.post_turn.SessionLocal", lambda: _FakeSessionCM(session)),
        patch(
            "app.services.chat.post_turn.messages_repo.create",
            AsyncMock(return_value=assistant),
        ),
        patch("app.services.chat.post_turn.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.post_turn.usage_repo.add_tokens", add_tokens),
        patch("app.services.chat.post_turn.quota_service.adjust_usage", AsyncMock()),
        patch(
            "app.services.chat.post_turn.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch("app.services.chat.post_turn.get_settings", return_value=Settings()),
        patch("app.services.chat.post_turn.clear_pending_finalize", AsyncMock()),
    ):
        await finalize_stream_turn_db(
            redis,
            ctx,
            "hello",
            {"input": 1_000_000, "output": 1_000_000},
            result={},
        )

    add_tokens.assert_awaited_once()
    assert add_tokens.await_args.kwargs["est_cost_usd"] == pytest.approx(0.14 + 0.28)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_step", ["create", "usage", "commit"])
async def test_failed_regenerate_preserves_original_attachment_bytes(failure_step):
    session = AsyncMock()
    old = MagicMock(id=uuid4())
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[],
        run_title=False,
        user_message_content="question",
        reserved_tokens=200,
        max_output_tokens=50,
        regenerate_backup=RegenerateBackup("original", "free-chat", old.id),
    )
    create = AsyncMock(return_value=MagicMock(id=uuid4()))
    add_usage = AsyncMock()
    {"create": create, "usage": add_usage, "commit": session.commit}[
        failure_step
    ].side_effect = RuntimeError("database unavailable")
    delete_bytes = AsyncMock()
    refund = AsyncMock()
    with (
        patch("app.services.chat.post_turn.SessionLocal", lambda: _FakeSessionCM(session)),
        patch("app.services.chat.post_turn.messages_repo.get_by_id", AsyncMock(return_value=old)),
        patch("app.services.chat.post_turn.messages_repo.create", create),
        patch("app.services.chat.post_turn.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.post_turn.usage_repo.add_tokens", add_usage),
        patch(
            "app.services.chat.post_turn.attachment_lifecycle.detach_attachments_for_messages",
            AsyncMock(return_value=["original.png"]),
        ),
        patch("app.services.chat.post_turn.attachment_lifecycle.delete_storage_keys", delete_bytes),
        patch("app.services.chat.post_turn.quota_service.refund_usage", refund),
        patch("app.services.chat.post_turn.get_settings", return_value=Settings(_env_file=None)),
    ):
        with pytest.raises(RuntimeError, match="database unavailable"):
            await finalize_stream_turn_db(
                AsyncMock(), ctx, "replacement", {"input": 10, "output": 5}, result={}
            )
    delete_bytes.assert_not_awaited()
    refund.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_success_does_not_depend_on_post_commit_refresh():
    session = AsyncMock()
    session.refresh.side_effect = RuntimeError("connection lost after commit")
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[],
        run_title=False,
        user_message_content="question",
        reserved_tokens=200,
        max_output_tokens=50,
    )
    refund = AsyncMock()
    adjust = AsyncMock()
    result = {}
    assistant_id = uuid4()
    with (
        patch("app.services.chat.post_turn.SessionLocal", lambda: _FakeSessionCM(session)),
        patch(
            "app.services.chat.post_turn.messages_repo.create",
            AsyncMock(return_value=MagicMock(id=assistant_id)),
        ),
        patch("app.services.chat.post_turn.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.post_turn.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.post_turn.quota_service.adjust_usage", adjust),
        patch("app.services.chat.post_turn.quota_service.refund_usage", refund),
        patch("app.services.chat.post_turn.get_settings", return_value=Settings(_env_file=None)),
    ):
        await finalize_stream_turn_db(
            AsyncMock(), ctx, "reply", {"input": 10, "output": 5}, result=result
        )
    session.commit.assert_awaited_once()
    assert result["message_id"] == str(assistant_id)
    adjust.assert_awaited_once()
    refund.assert_not_awaited()
