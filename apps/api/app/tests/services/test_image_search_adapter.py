"""Tests for the model-callable search_image MCP adapter."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.image_search import ImageSearchError
from app.services.mcp.image_search_adapter import ImageSearchAdapter, bind_image_search_context


def _settings(**kwargs: object) -> Settings:
    s = Settings()
    for key, value in kwargs.items():
        setattr(s, key, value)
    return s


@pytest.mark.asyncio
async def test_invoke_requires_bound_context():
    adapter = ImageSearchAdapter(_settings(image_search_enabled=True))
    result = await adapter.invoke({"query": "an ear"})
    assert "unavailable" in result.content.lower()


@pytest.mark.asyncio
async def test_invoke_missing_query():
    adapter = ImageSearchAdapter(_settings(image_search_enabled=True))
    user = MagicMock()
    with bind_image_search_context(user=user, redis=MagicMock(), chat_id=uuid4()):
        result = await adapter.invoke({"query": "   "})
    assert "missing query" in result.content.lower()


@pytest.mark.asyncio
async def test_invoke_disabled():
    adapter = ImageSearchAdapter(_settings(image_search_enabled=False))
    user = MagicMock()
    with bind_image_search_context(user=user, redis=MagicMock(), chat_id=uuid4()):
        result = await adapter.invoke({"query": "an ear"})
    assert "disabled" in result.content.lower()


@pytest.mark.asyncio
async def test_invoke_persists_and_returns_terminal_marker():
    adapter = ImageSearchAdapter(_settings(image_search_enabled=True))
    user = MagicMock()
    chat_id = uuid4()
    asst_id = uuid4()
    marker = f"[Image: /attachments/{uuid4()}/file]"
    asst = MagicMock(id=asst_id, content=marker, model="image-search-model")
    search = AsyncMock(return_value=(MagicMock(), asst))

    with (
        bind_image_search_context(user=user, redis=MagicMock(), chat_id=chat_id),
        patch(
            "app.services.mcp.image_search_adapter.image_search_service.search_and_attach_for_chat",
            search,
        ),
    ):
        result = await adapter.invoke({"query": "an ear"})

    search.assert_awaited_once()
    kwargs = search.await_args.kwargs
    assert kwargs["create_user_message"] is False
    assert kwargs["query"] == "an ear"
    assert result.data is not None
    assert result.data["terminal"] is True
    assert result.data["image_marker"] == marker
    assert result.data["assistant_message_id"] == str(asst_id)


@pytest.mark.asyncio
async def test_invoke_surfaces_search_error():
    adapter = ImageSearchAdapter(_settings(image_search_enabled=True))
    user = MagicMock()
    with (
        bind_image_search_context(user=user, redis=MagicMock(), chat_id=uuid4()),
        patch(
            "app.services.mcp.image_search_adapter.image_search_service.search_and_attach_for_chat",
            AsyncMock(side_effect=ImageSearchError("no photo found", status_code=502)),
        ),
    ):
        result = await adapter.invoke({"query": "an ear"})
    assert "failed" in result.content.lower()


@pytest.mark.asyncio
async def test_invoke_rejects_marker_without_image_prefix():
    adapter = ImageSearchAdapter(_settings(image_search_enabled=True))
    user = MagicMock()
    asst = MagicMock(id=uuid4(), content="oops not a marker")
    with (
        bind_image_search_context(user=user, redis=MagicMock(), chat_id=uuid4()),
        patch(
            "app.services.mcp.image_search_adapter.image_search_service.search_and_attach_for_chat",
            AsyncMock(return_value=(MagicMock(), asst)),
        ),
    ):
        result = await adapter.invoke({"query": "an ear"})
    assert "did not produce" in result.content.lower()
