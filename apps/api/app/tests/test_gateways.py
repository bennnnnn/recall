"""Tests for gateways: google_auth, mock_llm."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.google_auth import (
    GoogleAuthError,
    create_access_token,
    decode_access_token,
)
from app.gateways.mock_llm import (
    mock_memory_sections,
    mock_stream,
    mock_title,
    should_mock_llm,
)
from app.models.schemas import TodoExtractionResult

# ── mock_llm ───────────────────────────────────────────────────────────────────


def test_think_stripper_passes_plain_text_through():
    s = litellm_gateway._ThinkStripper()
    assert s.feed("hello ") + s.feed("world") + s.flush() == "hello world"


def test_think_stripper_removes_closed_think_block():
    s = litellm_gateway._ThinkStripper()
    open_tag = litellm_gateway._THINK_OPEN
    close_tag = litellm_gateway._THINK_CLOSE
    assert (
        s.feed(f"before {open_tag}reasoning here{close_tag} after") + s.flush() == "before  after"
    )


def test_think_stripper_handles_tag_split_across_chunks():
    s = litellm_gateway._ThinkStripper()
    open_tag = litellm_gateway._THINK_OPEN
    close_tag = litellm_gateway._THINK_CLOSE
    split = len(open_tag) // 2
    out = (
        s.feed(f"answer {open_tag[:split]}")
        + s.feed(f"{open_tag[split:]}wrong{close_tag} done")
        + s.flush()
    )
    assert out == "answer  done"


def test_think_stripper_drops_unclosed_block_on_flush():
    s = litellm_gateway._ThinkStripper()
    open_tag = litellm_gateway._THINK_OPEN
    assert s.feed(f"visible {open_tag}never closes") + s.flush() == "visible "


def test_think_stripper_recovers_after_oversized_unclosed_block():
    s = litellm_gateway._ThinkStripper()
    open_tag = litellm_gateway._THINK_OPEN
    oversized = "x" * (litellm_gateway._THINK_MAX_OPEN_BUFFER + 1)
    out = s.feed(f"keep {open_tag}{oversized}") + s.feed(" tail") + s.flush()
    assert out == "keep  tail"


@pytest.mark.asyncio
async def test_stream_chat_completion_wraps_acompletion_failure():
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")

    async def fail(**_kwargs):
        raise RuntimeError("network down")

    with patch("app.gateways.litellm_gateway.acompletion", fail):
        with pytest.raises(litellm_gateway.ModelUnavailableError, match="isn't responding"):
            async for _ in litellm_gateway.stream_chat_completion(
                settings=settings,
                model_alias="free-chat",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
            ):
                pass


def test_should_mock_llm_true_when_no_key():
    s = Settings(mock_llm_enabled=True, openrouter_api_key="")
    assert should_mock_llm(s) is True


def test_should_mock_llm_false_when_key_present():
    s = Settings(mock_llm_enabled=True, openrouter_api_key="sk-or-real")
    assert should_mock_llm(s) is False


def test_should_mock_llm_false_when_disabled():
    s = Settings(mock_llm_enabled=False, openrouter_api_key="")
    assert should_mock_llm(s) is False


@pytest.mark.asyncio
async def test_mock_stream_yields_words():
    tokens = [t async for t in mock_stream("hello world")]
    assert len(tokens) == 2
    assert "hello" in tokens[0]


@pytest.mark.asyncio
async def test_mock_title_uses_first_words():
    title = await mock_title("I love building AI apps really fast")
    assert title == "I love building AI"


@pytest.mark.asyncio
async def test_mock_title_empty():
    title = await mock_title("")
    assert title is None


@pytest.mark.asyncio
async def test_mock_memory_sections_short_message():
    result = await mock_memory_sections("hi", {})
    assert result is None


# ── complete_structured: bare-list wrapping ───────────────────────────────────


def _fake_completion(content: str):
    """A fake litellm acompletion response whose message.content is `content`."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_complete_structured_wraps_bare_empty_list():
    """Model returning `[]` for a single-list schema should validate to an empty
    result, not raise (regression for the noisy todo-extraction traceback)."""
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    with patch.object(
        litellm_gateway, "acompletion", AsyncMock(return_value=_fake_completion("[]"))
    ):
        result = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="memory-model",
            messages=[{"role": "user", "content": "x"}],
            schema=TodoExtractionResult,
        )
    assert result is not None
    assert isinstance(result, TodoExtractionResult)
    assert result.actions == []


@pytest.mark.asyncio
async def test_complete_structured_wraps_bare_list_with_items():
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    payload = '[{"action": "add", "topic": "Shopping", "content": "Buy milk"}]'
    with patch.object(
        litellm_gateway, "acompletion", AsyncMock(return_value=_fake_completion(payload))
    ):
        result = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="memory-model",
            messages=[{"role": "user", "content": "x"}],
            schema=TodoExtractionResult,
        )
    assert result is not None
    assert len(result.actions) == 1
    assert result.actions[0].content == "Buy milk"
    assert result.actions[0].topic == "Shopping"


@pytest.mark.asyncio
async def test_complete_structured_accepts_object_form():
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    payload = '{"actions": []}'
    with patch.object(
        litellm_gateway, "acompletion", AsyncMock(return_value=_fake_completion(payload))
    ):
        result = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="memory-model",
            messages=[{"role": "user", "content": "x"}],
            schema=TodoExtractionResult,
        )
    assert result is not None
    assert result.actions == []


# ── background LLM fallback on provider outage ───────────────────────────────


@pytest.mark.asyncio
async def test_complete_structured_retries_fallback_on_provider_outage():
    """When the primary model's acompletion raises, retry once against the
    fallback alias so a single-provider outage doesn't silently drop the job."""
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    payload = '{"actions": [{"action": "add", "topic": "T", "content": "C"}]}'
    calls: list[str] = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) == 1:
            raise RuntimeError("deepseek down")
        return _fake_completion(payload)

    with patch.object(litellm_gateway, "acompletion", AsyncMock(side_effect=fake_acompletion)):
        result = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="memory-model",
            messages=[{"role": "user", "content": "x"}],
            schema=TodoExtractionResult,
        )
    assert result is not None
    assert len(result.actions) == 1
    # First call used the primary model, second used the fallback.
    assert calls[0].endswith("deepseek-chat")
    assert calls[1].endswith("qwen-plus")


@pytest.mark.asyncio
async def test_complete_structured_no_retry_on_bad_output():
    """A successful call that returns unparseable JSON should NOT retry — the
    provider was up, the model just returned bad output, so the fallback won't help."""
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    calls: list[str] = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs["model"])
        return _fake_completion("not valid json {{{")

    with patch.object(litellm_gateway, "acompletion", AsyncMock(side_effect=fake_acompletion)):
        result = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="memory-model",
            messages=[{"role": "user", "content": "x"}],
            schema=TodoExtractionResult,
        )
    assert result is None
    assert len(calls) == 1  # no fallback attempt


@pytest.mark.asyncio
async def test_complete_structured_returns_none_when_both_fail():
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    calls: list[str] = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs["model"])
        raise RuntimeError("all providers down")

    with patch.object(litellm_gateway, "acompletion", AsyncMock(side_effect=fake_acompletion)):
        result = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="memory-model",
            messages=[{"role": "user", "content": "x"}],
            schema=TodoExtractionResult,
        )
    assert result is None
    assert len(calls) == 2  # primary + fallback both tried


@pytest.mark.asyncio
async def test_generate_title_retries_fallback_on_outage():
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    calls: list[str] = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) == 1:
            raise RuntimeError("title model down")
        return _fake_completion("My Cool Chat")

    with patch.object(litellm_gateway, "acompletion", AsyncMock(side_effect=fake_acompletion)):
        title = await litellm_gateway.generate_title(settings, "hello", "hi there")
    assert title == "My Cool Chat"
    assert len(calls) == 2
    result = await mock_memory_sections(
        "I am working on a Python FastAPI project for my startup",
        {},
    )
    assert result is not None
    assert len(result.sections) == 1
    assert result.sections[0].type == "focus"


@pytest.mark.asyncio
async def test_mock_todo_actions_add_and_complete():
    from app.gateways.mock_llm import mock_todo_actions

    result = await mock_todo_actions(
        "User: add buy milk\nAssistant: ok",
        [{"topic": "General", "content": "Old task", "checked": False}],
    )
    assert result is not None
    assert any(a.action == "add" for a in result.actions)

    done = await mock_todo_actions(
        "User: mark it done",
        [{"topic": "General", "content": "Old task", "checked": False}],
    )
    assert done is not None
    assert any(a.action == "complete" for a in done.actions)


@pytest.mark.asyncio
async def test_mock_todo_actions_delete_list():
    from app.gateways.mock_llm import mock_todo_actions

    result = await mock_todo_actions(
        "User: delete the shopping list",
        [{"topic": "Shopping", "content": "Eggs", "checked": False}],
    )
    assert result is not None
    assert result.actions[0].action == "delete_list"


def test_mock_llm_infer_list_title():
    from app.gateways.mock_llm import _infer_list_title

    assert _infer_list_title("add to my travel list") == "My Travel"


@pytest.mark.asyncio
async def test_mock_summary_concatenates_messages():
    from app.gateways.mock_llm import mock_summary

    summary = await mock_summary(
        "Prior context",
        [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there"}],
    )
    assert "Prior context" in summary
    assert "Hello" in summary


def test_mock_reply_for_messages():
    from app.gateways.mock_llm import mock_reply_for_messages

    reply = mock_reply_for_messages([{"role": "user", "content": "What is 2+2?"}])
    assert isinstance(reply, str)
    assert len(reply) > 0


def test_mock_reply_grades_quiz_letter_against_prior_fence():
    from app.gateways.mock_llm import MOCK_QUIZ_QUESTION, mock_reply_for_messages

    wrong = mock_reply_for_messages(
        [
            {"role": "assistant", "content": MOCK_QUIZ_QUESTION},
            {"role": "user", "content": "A"},
        ]
    )
    assert "Not quite" in wrong
    assert "```vocab_quiz" not in wrong
    assert "Tap another choice" in wrong

    right = mock_reply_for_messages(
        [
            {"role": "assistant", "content": MOCK_QUIZ_QUESTION},
            {"role": "user", "content": "B"},
        ]
    )
    assert "correct" in right.lower()
    assert "ephemeral" in right
    assert "```vocab_quiz" in right


def test_mock_reply_exhausts_after_three_wrong_tries():
    from app.gateways.mock_llm import MOCK_QUIZ_QUESTION, mock_reply_for_messages

    messages = [
        {"role": "assistant", "content": MOCK_QUIZ_QUESTION},
        {"role": "user", "content": "A"},
        {"role": "assistant", "content": "Not quite — tap another choice."},
        {"role": "user", "content": "C"},
        {"role": "assistant", "content": "Still wrong — another hint."},
        {"role": "user", "content": "D"},
    ]
    reply = mock_reply_for_messages(messages)
    assert "Out of tries" in reply
    assert "```vocab_quiz" in reply
    assert "ephemeral" in reply


@pytest.mark.asyncio
async def test_mock_rewrite_memory_sections():
    from app.gateways.mock_llm import mock_rewrite_memory_sections

    result = await mock_rewrite_memory_sections({"profile": "Lives in NYC"})
    assert result is not None
    assert len(result.sections) == 1


@pytest.mark.asyncio
async def test_mock_project_actions_create_project():
    from app.gateways.mock_llm import mock_project_actions

    transcript = "User: create project Spanish vocabulary\nAssistant: ok"
    result = await mock_project_actions(transcript, {"projects": []})
    assert result is not None
    assert any(a.action == "create_project" for a in result.actions)


@pytest.mark.asyncio
async def test_mock_project_actions_delete_project():
    from app.gateways.mock_llm import mock_project_actions

    transcript = "User: delete my English project"
    snapshot = {"projects": [{"title": "English", "kind": "language"}]}
    result = await mock_project_actions(transcript, snapshot)
    assert result is not None
    assert any(a.action == "delete_project" for a in result.actions)


def test_extract_quiz_word_and_answer():
    from app.gateways.mock_llm import _extract_quiz_answer, _extract_quiz_word

    transcript = "Assistant: **Word:** apple\nUser: B\nAssistant: correct!"
    assert _extract_quiz_word(transcript) == "apple"
    assert _extract_quiz_answer(transcript) == "B"


# ── google_auth JWT ─────────────────────────────────────────────────────────────


def test_create_and_decode_token():
    uid = uuid4()
    settings = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    token = create_access_token(uid, settings)
    decoded = decode_access_token(token, settings)
    assert decoded == uid


def test_decode_invalid_token_raises():
    settings = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    with pytest.raises(GoogleAuthError):
        decode_access_token("not-a-jwt", settings)


def test_decode_wrong_secret_raises():
    uid = uuid4()
    s1 = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    s2 = Settings(jwt_secret="different-secret-key-that-is-at-least-32ch!!")
    token = create_access_token(uid, s1)
    with pytest.raises(GoogleAuthError):
        decode_access_token(token, s2)


@pytest.mark.asyncio
async def test_verify_google_id_token_requires_email_verified():
    from unittest.mock import patch

    from app.gateways.google_auth import verify_google_id_token

    settings = Settings(google_client_id="test-client")
    payload = {"email_verified": False}
    with patch(
        "app.gateways.google_auth.id_token.verify_oauth2_token",
        return_value=payload,
    ):
        with pytest.raises(GoogleAuthError, match="not verified"):
            await verify_google_id_token("token", settings)


@pytest.mark.asyncio
async def test_verify_google_id_token_offloads_to_thread():
    """Sync Google cert/HTTP verify must run via asyncio.to_thread."""
    from unittest.mock import patch

    from app.gateways.google_auth import verify_google_id_token

    settings = Settings(google_client_id="test-client")
    payload = {"email_verified": True, "sub": "g-1", "email": "a@b.c"}
    calls: list[str] = []
    real_to_thread = asyncio.to_thread

    async def spy_to_thread(func, /, *args, **kwargs):
        calls.append(func.__name__)
        return await real_to_thread(func, *args, **kwargs)

    with (
        patch(
            "app.gateways.google_auth.id_token.verify_oauth2_token",
            return_value=payload,
        ),
        patch("app.gateways.google_auth.asyncio.to_thread", side_effect=spy_to_thread),
    ):
        out = await verify_google_id_token("token", settings)

    assert out == payload
    assert calls == ["_verify_google_id_token_sync"]


def test_litellm_kwargs_use_openrouter_key():
    from app.gateways import litellm_gateway

    settings = Settings(openrouter_api_key="sk-or")
    route = litellm_gateway.resolve_route("free-chat")
    kwargs = litellm_gateway._litellm_kwargs(settings, route)
    assert kwargs["api_key"] == "sk-or"
    assert "api_base" not in kwargs
    assert route.model == "openrouter/deepseek/deepseek-chat"
    assert "extra_headers" in kwargs


def test_litellm_openrouter_model_prefix():
    from app.services.model_catalog import litellm_openrouter_model

    assert litellm_openrouter_model("deepseek/deepseek-chat") == "openrouter/deepseek/deepseek-chat"
    assert litellm_openrouter_model("openrouter/auto") == "openrouter/openrouter/auto"


# ── deps: get_current_user ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_user_from_valid_token():
    from unittest.mock import AsyncMock, MagicMock, patch

    from fastapi.security import HTTPAuthorizationCredentials

    from app.core.deps import get_current_user

    uid = uuid4()
    settings = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    token = create_access_token(uid, settings)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    fake_user = MagicMock()
    with (
        patch("app.core.deps.tokens_service.verify_access_token", AsyncMock(return_value=uid)),
        patch("app.core.deps.auth_service.get_current_user", AsyncMock(return_value=fake_user)),
        patch("app.core.deps.get_settings", return_value=settings),
    ):
        user = await get_current_user(creds, AsyncMock(), settings)
    assert user is fake_user


@pytest.mark.asyncio
async def test_get_current_user_not_found_raises_401():
    from unittest.mock import AsyncMock, patch
    from uuid import uuid4

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    from app.core.deps import get_current_user

    uid = uuid4()
    settings = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")

    with (
        patch("app.core.deps.tokens_service.verify_access_token", AsyncMock(return_value=uid)),
        patch("app.core.deps.auth_service.get_current_user", AsyncMock(return_value=None)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(creds, AsyncMock(), settings)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises_401():
    from unittest.mock import AsyncMock, patch

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    from app.core.deps import get_current_user

    settings = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")

    with patch(
        "app.core.deps.tokens_service.verify_access_token",
        AsyncMock(side_effect=GoogleAuthError("Invalid token")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(creds, AsyncMock(), settings, AsyncMock())
    assert exc_info.value.status_code == 401
    assert "Invalid token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_stream_chat_completion_retries_fallback_alias():
    from app.gateways.litellm_gateway import ModelUnavailableError

    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    calls: list[str] = []

    async def fake_stream_once(**kwargs):
        alias = kwargs["model_alias"]
        calls.append(alias)
        if alias == "smart-chat":
            raise ModelUnavailableError("down", failed_alias=alias)
        yield "hello"

    with patch.object(litellm_gateway, "_stream_chat_once", fake_stream_once):
        stream_meta: dict[str, str] = {}
        tokens = [
            t
            async for t in litellm_gateway.stream_chat_completion(
                settings=settings,
                model_alias="smart-chat",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10,
                fallback_aliases=["free-chat"],
                stream_meta=stream_meta,
            )
        ]
    assert tokens == ["hello"]
    assert calls == ["smart-chat", "free-chat"]
    assert stream_meta["model_alias"] == "free-chat"


@pytest.mark.asyncio
async def test_stream_chat_once_times_out_hung_provider():
    from app.gateways.litellm_gateway import ModelUnavailableError

    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        chat_stream_timeout_seconds=1,
    )

    class HungStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(2)
            raise StopAsyncIteration

    with patch(
        "app.gateways.litellm_gateway.acompletion",
        AsyncMock(return_value=HungStream()),
    ):
        with pytest.raises(ModelUnavailableError) as exc_info:
            async for _ in litellm_gateway._stream_chat_once(
                settings=settings,
                model_alias="free-chat",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10,
            ):
                pass
    assert "isn't responding" in exc_info.value.message


@pytest.mark.asyncio
async def test_acompletion_with_fallback_times_out_hung_provider():
    """A hung background (non-streaming) LLM call must be aborted by the
    background timeout and fall back to the next alias rather than stalling
    the job worker."""
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        background_llm_timeout_seconds=1,
    )
    calls: list[str] = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs["model"])
        await asyncio.sleep(2)  # exceed the 1s timeout
        return _fake_completion("{}")

    with patch.object(litellm_gateway, "acompletion", AsyncMock(side_effect=fake_acompletion)):
        result = await litellm_gateway._acompletion_with_fallback(
            settings,
            "memory-model",
            messages=[{"role": "user", "content": "x"}],
            max_tokens=10,
        )
    # Both primary and fallback timed out → None.
    assert result is None
    assert len(calls) == 2
    assert calls[0].endswith("deepseek-chat")
    assert calls[1].endswith("qwen-plus")


@pytest.mark.asyncio
async def test_complete_structured_times_out_hung_provider():
    """complete_structured must abort a hung call via the background timeout
    and return None (after exhausting the fallback) instead of hanging."""
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        background_llm_timeout_seconds=1,
    )
    calls: list[str] = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs["model"])
        await asyncio.sleep(2)  # exceed the 1s timeout
        return _fake_completion("{}")

    with patch.object(litellm_gateway, "acompletion", AsyncMock(side_effect=fake_acompletion)):
        result = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="memory-model",
            messages=[{"role": "user", "content": "x"}],
            schema=TodoExtractionResult,
        )
    assert result is None
    # Primary timed out, then fallback also timed out.
    assert len(calls) == 2
    assert calls[0].endswith("deepseek-chat")
    assert calls[1].endswith("qwen-plus")
