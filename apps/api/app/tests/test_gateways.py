"""Tests for gateways: google_auth, mock_llm."""

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


@pytest.mark.asyncio
async def test_mock_memory_sections_long_message():
    result = await mock_memory_sections(
        "I am working on a Python FastAPI project for my startup",
        {},
    )
    assert result is not None
    assert len(result.sections) == 1
    assert result.sections[0].type == "focus"


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


def test_verify_google_id_token_requires_email_verified():
    from unittest.mock import patch

    from app.gateways.google_auth import verify_google_id_token

    settings = Settings(google_client_id="test-client")
    payload = {"email_verified": False}
    with patch(
        "app.gateways.google_auth.id_token.verify_oauth2_token",
        return_value=payload,
    ):
        with pytest.raises(GoogleAuthError, match="not verified"):
            verify_google_id_token("token", settings)


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
        patch("app.core.deps.decode_access_token", return_value=uid),
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
        patch("app.core.deps.decode_access_token", return_value=uid),
        patch("app.core.deps.auth_service.get_current_user", AsyncMock(return_value=None)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(creds, AsyncMock(), settings)
    assert exc_info.value.status_code == 401
