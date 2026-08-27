from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.tests.services.chat_test_support import (
    FakeSessionCM as _FakeSessionCM,
)
from app.tests.services.chat_test_support import (
    offline_session_patches as _offline_session_patches,
)
from app.tests.services.chat_test_support import (
    quiz_message_repo_patches as _quiz_message_repo_patches,
)

pytest_plugins = ("app.tests.services.chat_test_support",)


@pytest.mark.asyncio
async def test_stream_does_not_duplicate_user_message(stream_offline_io):
    from app.services import chat as chat_module

    tokens = ["Hello", " there"]

    async def fake_stream(**kwargs):
        for t in tokens:
            yield t

    user_id = AsyncMock()
    chat_id = AsyncMock()

    mock_build = AsyncMock(
        return_value=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "question"},
        ]
    )

    fake_user = MagicMock()
    fake_user.id = user_id
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=1)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch("app.services.chat.turn_prep.context.build_prompt_messages", mock_build),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=(None, [])),
        ),
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()),
    ):
        collected = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=user_id,
            chat_id=chat_id,
            content="question",
        ):
            collected.append(tok)

    assert collected == tokens
    assert mock_build.await_count == 1


@pytest.mark.asyncio
async def test_memory_extraction_runs_on_later_turn(stream_offline_io):
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "answer"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=3)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=(None, [])),
        ),
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        result: dict[str, str] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(
                max_output_tokens=100,
                memory_extract_every_n_turns=1,
                mcp_tool_loop_enabled=False,
            ),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="second turn info",
            result=result,
        ):
            pass
        finalize = result.get("_finalize_task")
        if finalize is not None:
            await finalize

    # Explicit every-turn setting still enqueues memory on later turns.
    job_types = [call.args[1] for call in enqueue_job.call_args_list]
    assert job_types.count("memory") == 1
    assert "topic" not in job_types
    assert "todos" not in job_types
    assert "projects" not in job_types


@pytest.mark.asyncio
async def test_memory_extraction_skipped_when_memory_disabled(stream_offline_io):
    """When the user has memory_enabled=False, the memory job must not be
    enqueued at all — previously it was enqueued every N turns and the
    extraction worker no-op'd internally, wasting a stream-job cycle."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "answer"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.memory_enabled = False

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=3)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=(None, [])),
        ),
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        result: dict[str, str] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="second turn info",
            result=result,
        ):
            pass
        finalize = result.get("_finalize_task")
        if finalize is not None:
            await finalize

    job_types = [call.args[1] for call in enqueue_job.call_args_list]
    assert "memory" not in job_types


@pytest.mark.asyncio
async def test_memory_extraction_throttled_when_every_n_gt_1(stream_offline_io):
    """Ops can still raise memory_extract_every_n_turns to skip intermediate turns."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "answer"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=2)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=(None, [])),
        ),
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        result: dict[str, str] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(
                max_output_tokens=100, memory_extract_every_n_turns=3, mcp_tool_loop_enabled=False
            ),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="turn two chit chat",
            result=result,
        ):
            pass
        finalize = result.get("_finalize_task")
        if finalize is not None:
            await finalize

    job_types = [call.args[1] for call in enqueue_job.call_args_list]
    assert "memory" not in job_types


@pytest.mark.asyncio
async def test_stream_skips_pre_reply_todo_llm_sync(stream_offline_io):
    """Todo LLM extraction must not block the chat path before streaming."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "ok"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=1)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.todos.extract.extract_todo_actions",
            AsyncMock(),
        ) as extract_mock,
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=(None, [])),
        ),
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
    ):
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="add eggs to groceries",
        ):
            pass

    extract_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_turn_jobs_enqueue_todos_when_transcript_matches(stream_offline_io):
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "Added eggs to your grocery list."

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=3)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=(None, [])),
        ),
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        result: dict[str, str] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="add eggs to groceries",
            result=result,
        ):
            pass
        finalize = result.get("_finalize_task")
        if finalize is not None:
            await finalize

    job_types = [call.args[1] for call in enqueue_job.call_args_list]
    assert "todos" in job_types
    assert result.get("todos_sync") == "1"


@pytest.mark.asyncio
async def test_stream_sets_final_content_on_cancel(stream_offline_io):
    """On a user-initiated stop, the server persists text the client may not have
    rendered yet; `result["final_content"]` carries the authoritative persisted
    text so the client can reconcile (stop/regenerate desync fix)."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        for w in ["one ", "two ", "three "]:
            yield w

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    cancel_after = {"n": 0}

    def should_cancel():
        cancel_after["n"] += 1
        return cancel_after["n"] > 1  # let the first token through, then cancel

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=3)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=(None, [])),
        ),
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()),
    ):
        result: dict[str, object] = {}
        yielded: list[str] = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="question",
            should_cancel=should_cancel,
            result=result,
        ):
            yielded.append(tok)
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    # Only the first token was yielded before cancel broke the loop.
    assert yielded == ["one "]
    # The authoritative persisted text is exposed for client reconciliation.
    assert result.get("final_content") == "one"


@pytest.mark.asyncio
async def test_cancelled_stream_skips_model_health_sample(stream_offline_io):
    """User stop must not record a failed health sample (poisons fallback routing)."""
    from uuid import uuid4

    from app.services.chat.stream import stream_and_finalize
    from app.services.chat.turn_prep import StreamContext

    async def fake_stream(**_kwargs):
        yield "one "
        yield "two "

    record = AsyncMock()
    cancel_after = {"n": 0}

    def should_cancel() -> bool:
        cancel_after["n"] += 1
        return cancel_after["n"] > 1

    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hi"}],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=100,
        max_output_tokens=50,
        skip_memory_jobs=True,
    )

    result: dict[str, object] = {}
    with ExitStack() as stack:
        stack.enter_context(
            patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream)
        )
        stack.enter_context(patch("app.services.model_health.record_sample", record))
        stack.enter_context(patch("app.services.chat.stream.finalize_stream_turn_db", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.calendar.materialize_calendar_proposals",
                AsyncMock(side_effect=lambda *_a, **_k: _a[-1]),
            )
        )
        stack.enter_context(patch("app.repositories.users.get_by_id", AsyncMock(return_value=None)))
        async for _ in stream_and_finalize(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            ctx,
            should_cancel=should_cancel,
            result=result,
        ):
            pass
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    record.assert_not_awaited()


@pytest.mark.asyncio
async def test_hard_cancel_before_tokens_skips_model_health_sample(stream_offline_io):
    """Cancel while waiting on the provider must not record success=False."""
    import asyncio
    from uuid import uuid4

    from app.services.chat.stream import stream_and_finalize
    from app.services.chat.turn_prep import StreamContext

    async def fake_stream(**_kwargs):
        raise asyncio.CancelledError()
        yield  # pragma: no cover

    record = AsyncMock()
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hi"}],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=100,
        max_output_tokens=50,
        skip_memory_jobs=True,
    )

    with ExitStack() as stack:
        stack.enter_context(
            patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream)
        )
        stack.enter_context(patch("app.services.model_health.record_sample", record))
        with pytest.raises(asyncio.CancelledError):
            async for _ in stream_and_finalize(
                AsyncMock(),
                Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
                ctx,
                should_cancel=None,
            ):
                pass

    record.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_response_rejects_empty_content(stream_offline_io):
    from app.exceptions import ChatNotFoundError
    from app.services.chat.stream import stream_chat_response

    with pytest.raises(ChatNotFoundError, match="empty"):
        async for _ in stream_chat_response(
            AsyncMock(),
            Settings(),
            user_id=uuid4(),
            chat_id=uuid4(),
            content="   ",
        ):
            pass


@pytest.mark.asyncio
async def test_try_image_gen_skips_recent_lookup_when_text_cannot_be_revision():
    from app.services.chat.stream import _try_image_gen_for_turn

    user = MagicMock()
    user.id = uuid4()
    list_recent = AsyncMock(return_value=[])
    long_text = "x" * 121

    with (
        patch("app.services.chat.stream.plan_service.is_pro", return_value=True),
        patch("app.services.chat.stream.extract_image_gen_prompt", return_value=None),
        patch("app.services.chat.stream.messages_repo.list_recent", list_recent),
    ):
        handled = await _try_image_gen_for_turn(
            Settings(),
            user=user,
            chat_id=uuid4(),
            content=long_text,
            result=None,
            create_user_message=True,
        )

    assert handled is False
    list_recent.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("greeting", ["hi", "hello", "thanks", "ok"])
async def test_try_image_gen_skips_recent_lookup_for_greeting(greeting: str):
    from app.services.chat.stream import _try_image_gen_for_turn

    user = MagicMock()
    user.id = uuid4()
    list_recent = AsyncMock(return_value=[])

    with (
        patch("app.services.chat.stream.plan_service.is_pro", return_value=True),
        patch("app.services.chat.stream.extract_image_gen_prompt", return_value=None),
        patch("app.services.chat.stream.messages_repo.list_recent", list_recent),
    ):
        handled = await _try_image_gen_for_turn(
            Settings(),
            user=user,
            chat_id=uuid4(),
            content=greeting,
            result=None,
            create_user_message=True,
        )

    assert handled is False
    list_recent.assert_not_awaited()


@pytest.mark.asyncio
async def test_try_image_gen_looks_up_recent_when_text_could_be_revision():
    from app.services.chat.stream import _try_image_gen_for_turn

    user = MagicMock()
    user.id = uuid4()
    list_recent = AsyncMock(return_value=[])

    with (
        patch("app.services.chat.stream.plan_service.is_pro", return_value=True),
        patch("app.services.chat.stream.extract_image_gen_prompt", return_value=None),
        patch("app.services.chat.stream.messages_repo.list_recent", list_recent),
    ):
        handled = await _try_image_gen_for_turn(
            Settings(),
            user=user,
            chat_id=uuid4(),
            content="make it blue",
            result=None,
            create_user_message=True,
        )

    assert handled is False
    list_recent.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [403, 404])
async def test_image_regen_soft_fail_keeps_prior_assistant(status_code: int):
    """403/404 must not delete the prior assistant (omit-until-success)."""
    from app.services.chat.stream import _try_image_gen_for_turn
    from app.services.image_generation import ImageGenerationError

    user = MagicMock()
    user.id = uuid4()
    old_id = uuid4()
    delete_message = AsyncMock()

    with (
        patch("app.services.chat.stream.plan_service.is_pro", return_value=True),
        patch("app.services.chat.stream.extract_image_gen_prompt", return_value="a cat"),
        patch("app.services.chat.stream.messages_repo.delete_message", delete_message),
        patch(
            "app.services.chat.stream.image_generation_service.generate_for_chat",
            AsyncMock(side_effect=ImageGenerationError("Not available", status_code=status_code)),
        ),
    ):
        handled = await _try_image_gen_for_turn(
            Settings(),
            user=user,
            chat_id=uuid4(),
            content="Generate image: a cat",
            result=None,
            create_user_message=False,
            replace_assistant_id=old_id,
        )

    assert handled is False
    delete_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_image_regen_deletes_prior_assistant_only_after_success():
    from app.services.chat.stream import _try_image_gen_for_turn

    user = MagicMock()
    user.id = uuid4()
    old_id = uuid4()
    chat_id = uuid4()
    old = MagicMock()
    old.id = old_id
    old.role = "assistant"
    asst_msg = MagicMock()
    asst_msg.id = uuid4()
    asst_msg.content = "[Image: /attachments/x/file]"
    asst_msg.model = "image-gen-model"
    order: list[str] = []

    async def generate_for_chat(*_args, **_kwargs):
        order.append("generate")
        return MagicMock(), asst_msg

    async def delete_message(_session, message):
        order.append(f"delete:{message.id}")

    async def purge_attachments_for_messages(_session, _settings, message_ids):
        order.append(f"purge:{message_ids[0]}")

    get_by_id = AsyncMock(return_value=old)

    with (
        patch("app.services.chat.stream.plan_service.is_pro", return_value=True),
        patch("app.services.chat.stream.extract_image_gen_prompt", return_value="a cat"),
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        patch("app.services.chat.stream.messages_repo.get_by_id", get_by_id),
        patch("app.services.chat.stream.messages_repo.delete_message", delete_message),
        patch(
            "app.services.chat.stream.attachment_lifecycle.purge_attachments_for_messages",
            purge_attachments_for_messages,
        ),
        patch(
            "app.services.chat.stream.image_generation_service.generate_for_chat",
            generate_for_chat,
        ),
    ):
        handled = await _try_image_gen_for_turn(
            Settings(),
            user=user,
            chat_id=chat_id,
            content="Generate image: a cat",
            result={},
            create_user_message=False,
            replace_assistant_id=old_id,
        )

    assert handled is True
    assert order == ["generate", f"purge:{old_id}", f"delete:{old_id}"]
    get_by_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_hard_cancel_with_partial_reply_finalizes(stream_offline_io):
    """WS/SSE CancelledError after tokens must persist like soft stop (no full refund)."""
    import asyncio
    from uuid import uuid4

    from app.services.chat.stream import stream_and_finalize
    from app.services.chat.turn_prep import StreamContext

    async def fake_stream(**_kwargs):
        yield "partial "
        raise asyncio.CancelledError()

    finalize = AsyncMock()
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hi"}],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=100,
        max_output_tokens=50,
        skip_memory_jobs=True,
    )
    result: dict[str, object] = {}

    with ExitStack() as stack:
        stack.enter_context(
            patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream)
        )
        stack.enter_context(patch("app.services.chat.stream.finalize_stream_turn_db", finalize))
        stack.enter_context(
            patch(
                "app.services.calendar.materialize_calendar_proposals",
                AsyncMock(side_effect=lambda *_a, **_k: _a[-1]),
            )
        )
        stack.enter_context(patch("app.repositories.users.get_by_id", AsyncMock(return_value=None)))
        tokens: list[str] = []
        async for tok in stream_and_finalize(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            ctx,
            should_cancel=None,
            result=result,
        ):
            tokens.append(tok)
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    assert tokens == ["partial "]
    assert result.get("final_content") == "partial"
    finalize.assert_awaited()


@pytest.mark.asyncio
async def test_hard_cancel_with_empty_reply_reraises(stream_offline_io):
    """CancelledError before any token must propagate so the caller refunds."""
    import asyncio
    from uuid import uuid4

    from app.services.chat.stream import stream_and_finalize
    from app.services.chat.turn_prep import StreamContext

    async def fake_stream(**_kwargs):
        raise asyncio.CancelledError()
        yield  # pragma: no cover — async generator

    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hi"}],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=100,
        max_output_tokens=50,
        skip_memory_jobs=True,
    )

    with (
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.stream.finalize_stream_turn_db", AsyncMock()) as finalize,
        pytest.raises(asyncio.CancelledError),
    ):
        async for _ in stream_and_finalize(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            ctx,
            should_cancel=None,
            result={},
        ):
            pass

    finalize.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_closes_llm_stream_on_cancel(stream_offline_io):
    """Stop generation must aclose the provider stream so upstream tokens stop accruing."""
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    class TrackedStream:
        def __init__(self) -> None:
            self.aclose_called = False

        def __call__(self, **_kwargs):
            return self

        def __aiter__(self):
            self._remaining = ["one ", "two ", "three "]
            return self

        async def __anext__(self):
            if not self._remaining:
                raise StopAsyncIteration
            return self._remaining.pop(0)

        async def aclose(self) -> None:
            self.aclose_called = True

    tracked = TrackedStream()
    cancel_after = {"n": 0}

    def should_cancel():
        cancel_after["n"] += 1
        return cancel_after["n"] > 1

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=3)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=(None, [])),
        ),
        patch("app.gateways.litellm_gateway.stream_chat_completion", tracked),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()),
    ):
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="question",
            should_cancel=should_cancel,
        ):
            pass

    assert tracked.aclose_called is True


@pytest.mark.asyncio
async def test_stream_places_query_without_location_prompts_to_enable(stream_offline_io):
    """A 'near me' places query with no user.location should yield a deterministic
    'enable location' instant reply and skip web search (no guessing)."""
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.location = ""  # no location set
    fake_user.location_enabled = False

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    augment = AsyncMock(return_value=(None, []))

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=0)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch("app.services.web_search.build_search_augmentation", augment),
        patch("app.gateways.litellm_gateway.stream_chat_completion", AsyncMock()),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()),
    ):
        yielded: list[str] = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="best restaurants near me",
        ):
            yielded.append(tok)

    # The instant reply is the enable-location prompt.
    assert any("Settings" in t and "location" in t.lower() for t in yielded), yielded
    # Web search must be skipped (no guessing "near me").
    augment.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_places_query_uses_client_location_without_profile(stream_offline_io):
    """Opted-in client GPS (no saved profile city) should run web search."""
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.location = ""
    fake_user.location_enabled = True

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    augment = AsyncMock(return_value=(None, []))

    async def fake_stream(**kwargs):
        yield "answer"

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.users.update", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=0)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch("app.services.web_search.build_search_augmentation", augment),
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()),
    ):
        yielded: list[str] = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="best restaurants near me",
            client_location="San Francisco, CA",
        ):
            yielded.append(tok)

    assert not any("Settings" in t for t in yielded), yielded
    augment.assert_awaited_once()
    assert augment.await_args.kwargs["user_location"] == "San Francisco, CA"


@pytest.mark.asyncio
async def test_stream_persists_raw_text_when_enrichment_fails(stream_offline_io):
    """Post-stream enrichment (calendar materialize, math fences, …) must not
    abort persistence — the user already saw streamed tokens."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "hello "
        yield "world"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    finalize = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)))
        stack.enter_context(
            patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user))
        )
        stack.enter_context(
            patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat))
        )
        stack.enter_context(
            patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=3))
        )
        stack.enter_context(patch("app.repositories.messages.create", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.build_prompt_messages",
                AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
            )
        )
        stack.enter_context(
            patch("app.services.calendar.is_connected", AsyncMock(return_value=False))
        )
        stack.enter_context(
            patch(
                "app.services.calendar.load_calendar_for_prompt",
                AsyncMock(return_value=None),
            )
        )
        stack.enter_context(
            patch(
                "app.services.calendar.materialize_calendar_proposals",
                AsyncMock(side_effect=RuntimeError("calendar boom")),
            )
        )
        stack.enter_context(patch("app.services.email.is_connected", AsyncMock(return_value=False)))
        stack.enter_context(
            patch("app.services.email.load_gmail_context", AsyncMock(return_value=None))
        )
        stack.enter_context(
            patch(
                "app.services.email.load_gmail_for_prompt",
                AsyncMock(return_value=None),
            )
        )
        stack.enter_context(
            patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[]))
        )
        stack.enter_context(
            patch(
                "app.services.web_search.build_search_augmentation",
                AsyncMock(return_value=(None, [])),
            )
        )
        stack.enter_context(
            patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream)
        )
        stack.enter_context(patch("app.services.quota.adjust_usage", AsyncMock()))
        stack.enter_context(patch("app.repositories.usage.add_tokens", AsyncMock()))
        stack.enter_context(patch("app.repositories.chats.touch_by_id", AsyncMock()))
        stack.enter_context(patch("app.core.jobs.enqueue", AsyncMock()))
        stack.enter_context(patch("app.services.chat.stream.finalize_stream_turn_db", finalize))

        result: dict[str, object] = {}
        collected: list[str] = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="question",
            result=result,
            user=fake_user,
        ):
            collected.append(tok)
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    assert collected == ["hello ", "world"]
    finalize.assert_awaited()
    assert finalize.await_args.args[2] == "hello world"


@pytest.mark.asyncio
async def test_stream_no_final_content_on_normal_completion(stream_offline_io):
    """`final_content` must NOT be set on a normal (non-cancelled) turn — keep
    `done` payloads small."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "answer"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    with (
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=3)),
        patch("app.repositories.messages.create", AsyncMock()),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.calendar.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.calendar.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.email.is_connected", AsyncMock(return_value=False)),
        patch("app.services.email.load_gmail_context", AsyncMock(return_value=None)),
        patch("app.services.email.load_gmail_for_prompt", AsyncMock(return_value=None)),
        patch("app.repositories.messages.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=(None, [])),
        ),
        patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.quota.adjust_usage", AsyncMock()),
        patch("app.repositories.usage.add_tokens", AsyncMock()),
        patch("app.repositories.chats.touch_by_id", AsyncMock()),
        patch("app.core.jobs.enqueue", AsyncMock()),
    ):
        result: dict[str, object] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="question",
            result=result,
        ):
            pass
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    assert "final_content" not in result


@pytest.mark.asyncio
async def test_stream_edit_response_yields_tokens():
    from app.services import chat as chat_module

    user_id = uuid4()
    chat_id = uuid4()
    message_id = uuid4()

    fake_user = MagicMock()
    fake_user.id = user_id
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary_message_count = 0  # no rolling summary yet on this chat

    fake_message = MagicMock()
    fake_message.id = message_id
    fake_message.role = "user"
    fake_message.created_at = MagicMock()

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    async def fake_stream(*args, **kwargs):
        yield "edited"

    with (
        patch("app.services.chat.stream.SessionLocal", return_value=session),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.get_by_id", AsyncMock(return_value=fake_message)),
        patch(
            "app.repositories.messages.ids_from_chat_at_or_after",
            AsyncMock(return_value=[message_id]),
        ),
        patch(
            "app.services.attachment_lifecycle.detach_attachments_for_messages",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.attachment_lifecycle.delete_storage_keys",
            AsyncMock(),
        ),
        patch("app.repositories.messages.delete_messages_from", AsyncMock()),
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch(
            "app.services.quota.daily_limit_for_user",
            MagicMock(return_value=500_000),
        ),
        patch("app.services.chat.stream.stream_chat_response", fake_stream),
    ):
        tokens = [
            tok
            async for tok in chat_module.stream_edit_response(
                AsyncMock(),
                Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                new_content="new question",
            )
        ]

    assert tokens == ["edited"]


@pytest.mark.asyncio
async def test_stream_edit_response_refunds_quota_when_delete_throws():
    """If the edit prep (delete/summary-reset) fails AFTER reserving quota,
    the reservation must be refunded before re-raising — otherwise the user
    is charged for a turn that never ran."""
    from app.services import chat as chat_module

    user_id = uuid4()
    chat_id = uuid4()
    message_id = uuid4()

    fake_user = MagicMock()
    fake_user.id = user_id
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary_message_count = 0

    fake_message = MagicMock()
    fake_message.id = message_id
    fake_message.role = "user"
    fake_message.created_at = MagicMock()

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    refund_mock = AsyncMock()

    with (
        patch("app.services.chat.stream.SessionLocal", return_value=session),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.get_by_id", AsyncMock(return_value=fake_message)),
        patch(
            "app.repositories.messages.ids_from_chat_at_or_after",
            AsyncMock(return_value=[message_id]),
        ),
        patch(
            "app.services.attachment_lifecycle.detach_attachments_for_messages",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.attachment_lifecycle.delete_storage_keys",
            AsyncMock(),
        ),
        patch(
            "app.repositories.messages.delete_messages_from",
            AsyncMock(side_effect=RuntimeError("delete failed")),
        ),
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.quota.refund_usage", refund_mock),
        patch(
            "app.services.quota.daily_limit_for_user",
            MagicMock(return_value=500_000),
        ),
    ):
        with pytest.raises(RuntimeError, match="delete failed"):
            async for _ in chat_module.stream_edit_response(
                AsyncMock(),
                Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                new_content="new question",
            ):
                pass

    refund_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_edit_response_keeps_storage_when_stream_fails():
    """Attachment files must not be deleted from object storage until the
    re-stream has actually produced output — otherwise a stream failure
    (model unavailable, disconnect, quota error) destroys user files for a
    turn that never replied. The message rows are still committed (the
    re-stream's recent window needs the tail gone), but the irrevocable R2
    delete is deferred until after the stream completes successfully."""
    from app.services import chat as chat_module

    user_id = uuid4()
    chat_id = uuid4()
    message_id = uuid4()

    fake_user = MagicMock()
    fake_user.id = user_id
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary_message_count = 0

    fake_message = MagicMock()
    fake_message.id = message_id
    fake_message.role = "user"
    fake_message.created_at = MagicMock()

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    async def _failing_stream(*args, **kwargs):
        raise RuntimeError("model unavailable")
        yield  # pragma: no cover - make this an async generator

    delete_storage_mock = AsyncMock()

    with (
        patch("app.services.chat.stream.SessionLocal", return_value=session),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.get_by_id", AsyncMock(return_value=fake_message)),
        patch(
            "app.repositories.messages.ids_from_chat_at_or_after",
            AsyncMock(return_value=[message_id]),
        ),
        patch(
            "app.services.attachment_lifecycle.detach_attachments_for_messages",
            AsyncMock(return_value=["user/attachments/abc.bin"]),
        ),
        patch("app.services.attachment_lifecycle.delete_storage_keys", delete_storage_mock),
        patch("app.repositories.messages.delete_messages_from", AsyncMock()),
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.quota.refund_usage", AsyncMock()),
        patch(
            "app.services.quota.daily_limit_for_user",
            MagicMock(return_value=500_000),
        ),
        patch("app.services.chat.stream.stream_chat_response", _failing_stream),
    ):
        with pytest.raises(RuntimeError, match="model unavailable"):
            async for _ in chat_module.stream_edit_response(
                AsyncMock(),
                Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                new_content="new question",
            ):
                pass

    # Storage files survived the failed turn — left for the orphan reaper.
    delete_storage_mock.assert_not_awaited()


async def _run_stream_edit_response(
    *, summary_message_count: int, total_before_edit: int, deleted_message_ids: list
):
    """Shared setup for the stale-summary-reset tests below — returns the
    fake_chat mock so callers can assert on chat.summary/summary_message_count.
    """
    from app.services import chat as chat_module

    user_id = uuid4()
    chat_id = uuid4()
    message_id = uuid4()

    fake_user = MagicMock()
    fake_user.id = user_id
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = "Existing rolling summary text."
    fake_chat.summary_message_count = summary_message_count

    fake_message = MagicMock()
    fake_message.id = message_id
    fake_message.role = "user"
    fake_message.created_at = MagicMock()

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    async def fake_stream(*args, **kwargs):
        yield "edited"

    with (
        patch("app.services.chat.stream.SessionLocal", return_value=session),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.repositories.messages.get_by_id", AsyncMock(return_value=fake_message)),
        patch(
            "app.repositories.messages.ids_from_chat_at_or_after",
            AsyncMock(return_value=deleted_message_ids),
        ),
        patch(
            "app.repositories.messages.count_for_chat",
            AsyncMock(return_value=total_before_edit),
        ),
        patch(
            "app.services.attachment_lifecycle.detach_attachments_for_messages",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.attachment_lifecycle.delete_storage_keys",
            AsyncMock(),
        ),
        patch("app.repositories.messages.delete_messages_from", AsyncMock()),
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)),
        patch(
            "app.services.quota.daily_limit_for_user",
            MagicMock(return_value=500_000),
        ),
        patch("app.services.chat.stream.stream_chat_response", fake_stream),
    ):
        async for _ in chat_module.stream_edit_response(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            new_content="new question",
        ):
            pass

    return fake_chat


@pytest.mark.asyncio
async def test_stream_edit_response_resets_stale_summary_when_edit_touches_summarized_prefix():
    """Regression test for the stale-summary bug: editing a message inside the
    already-summarized prefix must clear chat.summary/summary_message_count,
    or a rolling summary describing a deleted conversation branch would keep
    getting injected into every future prompt with nothing to ever fix it.
    """
    # 10 messages total before the edit; the edit deletes the last 8 (from
    # position 2 onward) — position 2 is inside the summarized prefix (5),
    # so the summary must be invalidated.
    fake_chat = await _run_stream_edit_response(
        summary_message_count=5,
        total_before_edit=10,
        deleted_message_ids=[uuid4() for _ in range(8)],
    )
    assert fake_chat.summary is None
    assert fake_chat.summary_message_count == 0


@pytest.mark.asyncio
async def test_stream_edit_response_keeps_summary_when_edit_is_after_summarized_prefix():
    """Editing a message that's entirely within the recent (never-summarized)
    window must NOT touch the still-accurate rolling summary."""
    # 10 messages total; the edit deletes only the last 2 (from position 8
    # onward) — position 8 is past the summarized prefix (5), so nothing
    # about the summarized range changed.
    fake_chat = await _run_stream_edit_response(
        summary_message_count=5,
        total_before_edit=10,
        deleted_message_ids=[uuid4() for _ in range(2)],
    )
    assert fake_chat.summary == "Existing rolling summary text."
    assert fake_chat.summary_message_count == 5


@pytest.mark.asyncio
async def test_regenerate_restores_assistant_when_stream_empty():
    """If regenerate deletes the prior assistant but the model returns nothing,
    the old reply is restored so the chat is not left blank."""
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.timezone = None

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    fake_last = MagicMock()
    fake_last.role = "assistant"
    fake_last.id = MagicMock()
    fake_last.content = "prior answer"
    fake_last.model = "free-chat"

    fake_last_user = MagicMock()
    fake_last_user.content = "question"

    restore = AsyncMock()

    async def empty_stream(**kwargs):
        if False:
            yield ""

    with ExitStack() as stack:
        for patcher in _offline_session_patches():
            stack.enter_context(patcher)
        for patcher in _quiz_message_repo_patches():
            stack.enter_context(patcher)
        stack.enter_context(
            patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user))
        )
        stack.enter_context(
            patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat))
        )
        stack.enter_context(
            patch("app.repositories.messages.get_last", AsyncMock(return_value=fake_last))
        )
        stack.enter_context(
            patch(
                "app.repositories.messages.get_last_user",
                AsyncMock(return_value=fake_last_user),
            )
        )
        stack.enter_context(
            patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=2))
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.build_prompt_messages",
                AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.web_search.is_vocab_quiz_answer",
                MagicMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.services.web_search.is_places_list_query",
                MagicMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.services.calendar.has_write_access",
                AsyncMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.repositories.messages.recent_user_contents",
                AsyncMock(return_value=[]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.fetch_web_and_tools",
                AsyncMock(return_value=(None, None, [], None)),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.inject_web_and_tools",
                AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
            )
        )
        stack.enter_context(patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)))
        stack.enter_context(patch("app.services.quota.refund_usage", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.attachment_lifecycle.detach_attachments_for_messages",
                AsyncMock(return_value=[]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.attachment_lifecycle.delete_storage_keys",
                AsyncMock(),
            )
        )
        stack.enter_context(patch("app.repositories.messages.delete_message", AsyncMock()))
        stack.enter_context(
            patch("app.gateways.litellm_gateway.stream_chat_completion", empty_stream)
        )
        stack.enter_context(patch("app.services.chat.stream.restore_regenerate_backup", restore))
        from app.gateways.litellm_gateway import ModelUnavailableError

        with pytest.raises(ModelUnavailableError, match="isn't responding"):
            async for _ in chat_module.stream_regenerate_response(
                AsyncMock(),
                Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
                user_id=fake_user.id,
                chat_id=MagicMock(),
            ):
                pass

    restore.assert_awaited_once()
    backup = restore.await_args.args[2]
    assert backup.content == "prior answer"
    assert backup.model == "free-chat"


@pytest.mark.asyncio
async def test_regenerate_omits_assistant_from_prompt_without_pre_delete():
    """Prior assistant stays in DB until finalize; prompt build must omit it."""
    from app.services import chat as chat_module
    from app.services.chat.turn_prep import ClientGeoContext, TurnPromptBundle

    captured: dict[str, object] = {}

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.timezone = None

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    fake_last = MagicMock()
    fake_last.role = "assistant"
    fake_last.id = MagicMock()
    fake_last.content = "prior answer"
    fake_last.model = "free-chat"

    fake_last_user = MagicMock()
    fake_last_user.content = "question"

    async def track_build(*_args, **kwargs):
        captured["omit"] = kwargs.get("omit_message_ids")
        return TurnPromptBundle(
            prompt_messages=[{"role": "system", "content": "sys"}],
            meta={},
            instant_reply=None,
            search_sources=[],
            local_places=False,
            max_out=100,
            fallback_models=[],
            minimal_quiz=False,
            minimal_vocab_answer=False,
            active_vocab_turn=False,
            lightweight=False,
            rich_context=True,
            quiz_grade=None,
            geo=ClientGeoContext(
                user_location=None,
                client_lat=None,
                client_lng=None,
                has_geo_fix=False,
                geo_query=False,
                ambiguous_nearby=False,
                local_places=False,
            ),
            local_tz="UTC",
            verified_math=None,
        )

    async def empty_stream(**kwargs):
        if False:
            yield ""

    delete_mock = AsyncMock()

    with ExitStack() as stack:
        for patcher in _offline_session_patches():
            stack.enter_context(patcher)
        for patcher in _quiz_message_repo_patches():
            stack.enter_context(patcher)
        stack.enter_context(
            patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user))
        )
        stack.enter_context(
            patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat))
        )
        stack.enter_context(
            patch("app.repositories.messages.get_last", AsyncMock(return_value=fake_last))
        )
        stack.enter_context(
            patch(
                "app.repositories.messages.get_last_user",
                AsyncMock(return_value=fake_last_user),
            )
        )
        stack.enter_context(
            patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=2))
        )
        stack.enter_context(
            patch(
                "app.services.chat.stream.build_stream_prompt_context",
                side_effect=track_build,
            )
        )
        stack.enter_context(patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)))
        stack.enter_context(patch("app.services.quota.refund_usage", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.attachment_lifecycle.detach_attachments_for_messages",
                AsyncMock(return_value=[]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.attachment_lifecycle.delete_storage_keys",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.repositories.messages.delete_message",
                delete_mock,
            )
        )
        stack.enter_context(
            patch("app.gateways.litellm_gateway.stream_chat_completion", empty_stream)
        )
        stack.enter_context(
            patch("app.services.chat.stream.restore_regenerate_backup", AsyncMock())
        )
        from app.gateways.litellm_gateway import ModelUnavailableError

        with pytest.raises(ModelUnavailableError):
            async for _ in chat_module.stream_regenerate_response(
                AsyncMock(),
                Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
                user_id=fake_user.id,
                chat_id=MagicMock(),
            ):
                pass

    assert captured["omit"] == {fake_last.id}
    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_regenerate_passes_client_geo_to_web_search():
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.timezone = None
    fake_user.locale = "en"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    fake_last = MagicMock()
    fake_last.role = "assistant"
    fake_last.id = MagicMock()
    fake_last.content = "old"
    fake_last.model = "free-chat"

    fake_last_user = MagicMock()
    fake_last_user.content = "Best restaurants near me"

    fetch_web = AsyncMock(return_value=(None, None, [], None))

    async def empty_stream(**kwargs):
        if False:
            yield ""

    with ExitStack() as stack:
        for patcher in _offline_session_patches():
            stack.enter_context(patcher)
        for patcher in _quiz_message_repo_patches():
            stack.enter_context(patcher)
        stack.enter_context(
            patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user))
        )
        stack.enter_context(
            patch("app.repositories.chats.get_by_id", AsyncMock(return_value=fake_chat))
        )
        stack.enter_context(
            patch("app.repositories.messages.get_last", AsyncMock(return_value=fake_last))
        )
        stack.enter_context(
            patch(
                "app.repositories.messages.get_last_user",
                AsyncMock(return_value=fake_last_user),
            )
        )
        stack.enter_context(
            patch("app.repositories.messages.count_for_chat", AsyncMock(return_value=2))
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.build_prompt_messages",
                AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.web_search.is_vocab_quiz_answer",
                MagicMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.services.calendar.has_write_access",
                AsyncMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.repositories.messages.recent_user_contents",
                AsyncMock(return_value=[]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.fetch_web_and_tools",
                fetch_web,
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.inject_web_and_tools",
                AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
            )
        )
        stack.enter_context(patch("app.services.quota.reserve_usage", AsyncMock(return_value=True)))
        stack.enter_context(patch("app.services.quota.refund_usage", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.attachment_lifecycle.detach_attachments_for_messages",
                AsyncMock(return_value=[]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.attachment_lifecycle.delete_storage_keys",
                AsyncMock(),
            )
        )
        stack.enter_context(patch("app.repositories.messages.delete_message", AsyncMock()))
        stack.enter_context(
            patch("app.gateways.litellm_gateway.stream_chat_completion", empty_stream)
        )
        stack.enter_context(
            patch("app.services.chat.stream.restore_regenerate_backup", AsyncMock())
        )
        from app.gateways.litellm_gateway import ModelUnavailableError

        with pytest.raises(ModelUnavailableError):
            async for _ in chat_module.stream_regenerate_response(
                AsyncMock(),
                Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
                user_id=fake_user.id,
                chat_id=MagicMock(),
                client_location="San Francisco, CA",
                client_latitude=37.77,
                client_longitude=-122.42,
            ):
                pass

    fetch_web.assert_awaited_once()
    assert fetch_web.await_args.kwargs["latitude"] == 37.77
    assert fetch_web.await_args.kwargs["longitude"] == -122.42
    assert fetch_web.await_args.kwargs["user_location"] == "San Francisco, CA"


@pytest.mark.asyncio
async def test_instant_reply_usage_uses_input_output_keys(stream_offline_io):
    """Instant replies must seed usage with ``input``/``output`` — the keys
    ``finalize_stream_turn_db`` reads. ``input_tokens``/``output_tokens`` were
    ignored, so quota fell back to full prompt re-estimation and overcharged."""
    from uuid import uuid4

    from app.services.chat.stream import stream_and_finalize
    from app.services.chat.turn_prep import StreamContext

    captured: dict[str, object] = {}

    async def capture_finalize(_redis, _ctx, assistant_text, usage, _result):
        captured["usage"] = dict(usage)
        captured["assistant_text"] = assistant_text

    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "what time is it?"}],
        run_title=False,
        user_message_content="what time is it?",
        reserved_tokens=100,
        max_output_tokens=50,
        instant_reply="It's 3:00 PM.",
        skip_memory_jobs=True,
    )

    result: dict[str, object] = {}
    with (
        patch("app.services.chat.stream.finalize_stream_turn_db", side_effect=capture_finalize),
        patch(
            "app.services.calendar.materialize_calendar_proposals",
            AsyncMock(side_effect=lambda *_a, **_k: _a[-1] if _a else "It's 3:00 PM."),
        ),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=None)),
    ):
        tokens: list[str] = []
        async for tok in stream_and_finalize(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            ctx,
            should_cancel=None,
            result=result,
        ):
            tokens.append(tok)
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    assert tokens == ["It's 3:00 PM."]
    assert "usage" in captured
    usage = captured["usage"]
    assert isinstance(usage, dict)
    assert "input" in usage and "output" in usage
    assert "input_tokens" not in usage and "output_tokens" not in usage
    # Instant replies skip the LLM entirely (canned time/location/not-connected
    # answers) — no provider token cost, so quota is not charged: 0/0 seeds
    # let finalize's adjust_usage refund the full reservation.
    assert usage["input"] == 0
    assert usage["output"] == 0


@pytest.mark.asyncio
async def test_web_search_tool_round_streams_final_instead_of_regenerating(
    stream_offline_io,
):
    """After web_search tools run, the visible answer is streamed — not a
    leftover complete_with_tools dumped as one instant_reply chunk."""
    from app.services.chat.stream import stream_and_finalize
    from app.services.chat.turn_prep import StreamContext

    query = "What's the latest news on SpaceX?"
    prompt = [{"role": "user", "content": query}]
    after_tools = [
        *prompt,
        {"role": "assistant", "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "tool_call_id": "c1", "content": "SpaceX landed Starship."},
    ]
    stream_messages: list[list[dict]] = []

    async def fake_stream(**kwargs):
        stream_messages.append(kwargs["messages"])
        yield "SpaceX "
        yield "landed."

    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=prompt,
        run_title=False,
        user_message_content=query,
        reserved_tokens=100,
        max_output_tokens=50,
        skip_memory_jobs=True,
    )
    result: dict[str, object] = {}
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.services.tool_loop.run_tool_rounds",
                AsyncMock(return_value=(after_tools, None, None)),
            )
        )
        stack.enter_context(
            patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False))
        )
        stack.enter_context(
            patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream)
        )
        stack.enter_context(patch("app.services.chat.stream.finalize_stream_turn_db", AsyncMock()))
        stack.enter_context(patch("app.services.model_health.record_sample", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.calendar.materialize_calendar_proposals",
                AsyncMock(side_effect=lambda *_a, **_k: _a[-1]),
            )
        )
        stack.enter_context(patch("app.repositories.users.get_by_id", AsyncMock(return_value=None)))
        yielded: list[str] = []
        async for tok in stream_and_finalize(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=True),
            ctx,
            should_cancel=None,
            result=result,
        ):
            yielded.append(tok)
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    assert yielded == ["SpaceX ", "landed."]
    assert ctx.instant_reply is None
    assert stream_messages == [after_tools]
