"""Per-chat Redis prepare/turn lock on stream_chat_response / regenerate."""

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import ChatBusyError, QuotaExceededError
from app.services.chat import stream as stream_module
from app.services.chat.stream_events import error_payload_for_exception


class _FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return False


def _user() -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.default_model = "free-chat"
    user.plan = "free"
    return user


def _chat() -> MagicMock:
    chat = MagicMock()
    chat.project_id = None
    chat.quiz_mode = None
    chat.summary = None
    return chat


@contextmanager
def _turn_load():
    chat = _chat()
    with (
        patch("app.services.chat.stream.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch("app.services.chat.stream.messages_repo.list_recent", AsyncMock(return_value=[])),
        patch("app.services.chat.stream.messages_repo.count_for_chat", AsyncMock(return_value=0)),
    ):
        yield


@pytest.mark.asyncio
async def test_stream_chat_acquire_fail_skips_prepare_and_raises_busy():
    user = _user()
    redis = AsyncMock()
    prepare = AsyncMock()
    wait = AsyncMock()
    release = AsyncMock()
    refund = AsyncMock()

    with (
        patch(
            "app.services.chat.stream.acquire_lock",
            AsyncMock(return_value=None),
        ) as acquire,
        patch("app.services.chat.stream.release_lock", release),
        patch("app.services.chat.stream.wait_for_pending_finalize", wait),
        patch("app.services.chat.stream.prepare_chat_turn", prepare),
        patch("app.services.chat.stream.quota_service.refund_usage", refund),
    ):
        with pytest.raises(ChatBusyError):
            async for _ in stream_module.stream_chat_response(
                redis,
                Settings(),
                user_id=user.id,
                chat_id=uuid4(),
                content="hi",
                user=user,
                skip_usage_seed=True,
            ):
                pass

    acquire.assert_awaited_once()
    key = acquire.await_args.args[1]
    assert key.startswith("chatprep:")
    assert acquire.await_args.args[2] == 120
    wait.assert_not_awaited()
    prepare.assert_not_awaited()
    release.assert_not_awaited()
    # Quota is reserved inside the turn_resources block, i.e. only after the
    # lock is held — a busy chat cannot have reserved anything to leak.
    refund.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_releases_lock_on_success():
    user = _user()
    redis = AsyncMock()
    chat_id = uuid4()
    release = AsyncMock()

    async def fake_stream(*_a, **_k):
        yield "ok"

    with (
        patch(
            "app.services.chat.stream.acquire_lock",
            AsyncMock(return_value="tok"),
        ) as acquire,
        patch("app.services.chat.stream.release_lock", release),
        patch("app.services.chat.stream.wait_for_pending_finalize", AsyncMock()),
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        _turn_load(),
        patch(
            "app.services.chat.stream.plan_service.resolve_user_model_override",
            return_value="free-chat",
        ),
        patch(
            "app.services.chat.stream.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch(
            "app.services.chat.stream._try_image_gen_for_turn",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.chat.stream.prepare_chat_turn",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("app.services.chat.stream.stream_and_finalize", fake_stream),
        patch("app.services.chat.stream.reserve_turn_quota", AsyncMock(return_value=100)),
    ):
        tokens = [
            t
            async for t in stream_module.stream_chat_response(
                redis,
                Settings(),
                user_id=user.id,
                chat_id=chat_id,
                content="hi",
                user=user,
                skip_usage_seed=True,
            )
        ]

    assert tokens == ["ok"]
    acquire.assert_awaited_once_with(redis, f"chatprep:{chat_id}", 120)
    release.assert_awaited_once_with(redis, f"chatprep:{chat_id}", "tok")


@pytest.mark.asyncio
async def test_stream_chat_releases_lock_when_prepare_fails():
    user = _user()
    redis = AsyncMock()
    chat_id = uuid4()
    release = AsyncMock()
    refund = AsyncMock()

    with (
        patch(
            "app.services.chat.stream.acquire_lock",
            AsyncMock(return_value="tok"),
        ),
        patch("app.services.chat.stream.release_lock", release),
        patch("app.services.chat.stream.wait_for_pending_finalize", AsyncMock()),
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        _turn_load(),
        patch(
            "app.services.chat.stream.plan_service.resolve_user_model_override",
            return_value="free-chat",
        ),
        patch(
            "app.services.chat.stream.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch(
            "app.services.chat.stream._try_image_gen_for_turn",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.chat.stream.prepare_chat_turn",
            AsyncMock(side_effect=RuntimeError("prepare boom")),
        ),
        patch("app.services.chat.stream.quota_service.refund_usage", refund),
        patch("app.services.chat.stream.reserve_turn_quota", AsyncMock(return_value=100)),
    ):
        with pytest.raises(RuntimeError, match="prepare boom"):
            async for _ in stream_module.stream_chat_response(
                redis,
                Settings(),
                user_id=user.id,
                chat_id=chat_id,
                content="hi",
                user=user,
                skip_usage_seed=True,
            ):
                pass

    release.assert_awaited_once_with(redis, f"chatprep:{chat_id}", "tok")
    refund.assert_awaited_once()


@pytest.mark.asyncio
async def test_regenerate_acquires_chatprep_lock():
    user = _user()
    redis = AsyncMock()
    chat_id = uuid4()
    release = AsyncMock()

    fake_chat = MagicMock()
    fake_chat.project_id = None
    fake_last = MagicMock()
    fake_last.role = "assistant"
    fake_last.id = uuid4()
    fake_last.content = "prior"
    fake_last.model = "free-chat"
    fake_last_user = MagicMock()
    fake_last_user.content = "question"

    async def fake_stream(*_a, **_k):
        yield "regen"

    with (
        patch(
            "app.services.chat.stream.acquire_lock",
            AsyncMock(return_value="tok"),
        ) as acquire,
        patch("app.services.chat.stream.release_lock", release),
        patch("app.services.chat.stream.wait_for_pending_finalize", AsyncMock()),
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.stream.users_repo.get_by_id",
            AsyncMock(return_value=user),
        ),
        patch(
            "app.services.chat.stream.chats_repo.get_by_id",
            AsyncMock(return_value=fake_chat),
        ),
        patch(
            "app.services.chat.stream.messages_repo.get_last",
            AsyncMock(return_value=fake_last),
        ),
        patch(
            "app.services.chat.stream.messages_repo.get_last_user",
            AsyncMock(return_value=fake_last_user),
        ),
        patch(
            "app.services.chat.stream.messages_repo.count_for_chat",
            AsyncMock(return_value=2),
        ),
        patch(
            "app.services.chat.stream.plan_service.resolve_user_model_override",
            return_value="free-chat",
        ),
        patch(
            "app.services.chat.stream._try_image_gen_for_turn",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.chat.stream.build_stream_prompt_context",
            AsyncMock(
                return_value=MagicMock(
                    max_out=100,
                    minimal_quiz=False,
                    prompt_messages=[],
                    meta={},
                    instant_reply=None,
                    search_sources=[],
                    local_places=False,
                    fallback_models=[],
                    minimal_vocab_answer=False,
                    active_vocab_turn=False,
                    quiz_grade=None,
                    geo=MagicMock(),
                    local_tz="UTC",
                    verified_math=None,
                )
            ),
        ),
        patch(
            "app.services.chat.stream.reserve_turn_quota",
            AsyncMock(return_value=50),
        ),
        patch(
            "app.services.chat.stream.stream_context_from_bundle",
            MagicMock(return_value=MagicMock()),
        ),
        patch("app.services.chat.stream.stream_and_finalize", fake_stream),
    ):
        tokens = [
            t
            async for t in stream_module.stream_regenerate_response(
                redis,
                Settings(),
                user_id=user.id,
                chat_id=chat_id,
            )
        ]

    assert tokens == ["regen"]
    acquire.assert_awaited_once_with(redis, f"chatprep:{chat_id}", 120)
    release.assert_awaited_once_with(redis, f"chatprep:{chat_id}", "tok")


def test_chat_busy_error_maps_to_busy_code():
    payload = error_payload_for_exception(ChatBusyError())
    assert payload == {
        "type": "error",
        "code": "busy",
        "message": "Still generating — wait or cancel first.",
    }


@pytest.mark.asyncio
async def test_turn_resources_refreshes_lock_while_held():
    redis = AsyncMock()
    refresh = AsyncMock()
    release = AsyncMock()

    with (
        patch("app.services.chat.stream.acquire_lock", AsyncMock(return_value="tok")),
        patch("app.services.chat.stream.refresh_lock", refresh),
        patch("app.services.chat.stream.release_lock", release),
        patch.object(stream_module, "_CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS", 0.05),
    ):
        async with stream_module.turn_resources(redis, user_id=uuid4(), chat_id=uuid4()):
            await asyncio.sleep(0.14)

    assert refresh.await_count >= 2
    release.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn_resources_borrowed_does_not_start_refresh():
    redis = AsyncMock()
    refresh = AsyncMock()
    chat_id = uuid4()
    borrowed = stream_module.TurnResources(
        redis=redis,
        user_id=uuid4(),
        chat_id=chat_id,
        lock_key=f"chatprep:{chat_id}",
        lock_token="outer",
        reserved_tokens=10,
    )

    with (
        patch("app.services.chat.stream.refresh_lock", refresh),
        patch.object(stream_module, "_CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS", 0.05),
    ):
        async with stream_module.turn_resources(
            redis,
            user_id=borrowed.user_id,
            chat_id=chat_id,
            borrowed=borrowed,
        ):
            await asyncio.sleep(0.12)

    refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_top_up_reserve_for_prompt_adds_delta():
    user = _user()
    redis = AsyncMock()
    res = stream_module.TurnResources(
        redis=redis,
        user_id=user.id,
        chat_id=uuid4(),
        lock_key="k",
        lock_token="t",
        reserved_tokens=10,
    )
    ctx = MagicMock()
    ctx.prompt_messages = [{"role": "user", "content": "hello"}]
    ctx.model = "free-chat"
    ctx.max_output_tokens = 50
    ctx.user = user
    ctx.reserved_tokens = 10

    with (
        patch("app.services.chat.stream.prompt_weighted_reserve_tokens", return_value=40),
        patch(
            "app.services.chat.stream.quota_service.reserve_usage",
            AsyncMock(return_value=True),
        ) as reserve,
    ):
        await stream_module._top_up_reserve_for_prompt(
            res, settings=Settings(), ctx=ctx, daily_limit=100
        )

    reserve.assert_awaited_once()
    assert reserve.await_args.args[2] == 30
    assert res.reserved_tokens == 40
    assert ctx.reserved_tokens == 40


@pytest.mark.asyncio
async def test_top_up_reserve_for_prompt_raises_when_over_limit():
    user = _user()
    redis = AsyncMock()
    res = stream_module.TurnResources(
        redis=redis,
        user_id=user.id,
        chat_id=uuid4(),
        lock_key="k",
        lock_token="t",
        reserved_tokens=10,
    )
    ctx = MagicMock()
    ctx.prompt_messages = [{"role": "user", "content": "hello"}]
    ctx.model = "free-chat"
    ctx.max_output_tokens = 50
    ctx.user = user
    ctx.reserved_tokens = 10

    with (
        patch("app.services.chat.stream.prompt_weighted_reserve_tokens", return_value=40),
        patch(
            "app.services.chat.stream.quota_service.reserve_usage",
            AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(QuotaExceededError):
            await stream_module._top_up_reserve_for_prompt(
                res, settings=Settings(), ctx=ctx, daily_limit=100
            )

    assert res.reserved_tokens == 10
    assert ctx.reserved_tokens == 10
