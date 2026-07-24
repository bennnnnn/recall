"""Tests for the model-callable generate_image MCP adapter."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways.mcp.image_gen_adapter import ImageGenAdapter, bind_image_gen_context
from app.services.image_generation import ImageGenerationError


def _settings(**kwargs: object) -> Settings:
    s = Settings()
    for key, value in kwargs.items():
        setattr(s, key, value)
    return s


@pytest.mark.asyncio
async def test_invoke_requires_bound_context():
    adapter = ImageGenAdapter(_settings(image_generation_enabled=True))
    result = await adapter.invoke({"prompt": "a cat"})
    assert "unavailable" in result.content.lower()


@pytest.mark.asyncio
async def test_invoke_rejects_non_pro():
    adapter = ImageGenAdapter(_settings(image_generation_enabled=True))
    user = MagicMock()
    with (
        bind_image_gen_context(user=user, redis=MagicMock(), chat_id=uuid4()),
        patch(
            "app.gateways.mcp.image_gen_adapter.plan_service.is_pro",
            return_value=False,
        ),
    ):
        result = await adapter.invoke({"prompt": "a cat"})
    assert "Pro" in result.content


@pytest.mark.asyncio
async def test_invoke_persists_and_returns_terminal_marker():
    adapter = ImageGenAdapter(_settings(image_generation_enabled=True))
    user = MagicMock()
    chat_id = uuid4()
    asst_id = uuid4()
    marker = f"[Image: /attachments/{uuid4()}/file]"
    asst = MagicMock(id=asst_id, content=marker, model="image-gen-model")
    generate = AsyncMock(return_value=(MagicMock(), asst))

    with (
        bind_image_gen_context(user=user, redis=MagicMock(), chat_id=chat_id),
        patch(
            "app.gateways.mcp.image_gen_adapter.plan_service.is_pro",
            return_value=True,
        ),
        patch(
            "app.gateways.mcp.image_gen_adapter.image_generation_service.generate_for_chat",
            generate,
        ),
    ):
        result = await adapter.invoke({"prompt": "watercolor fox", "aspect_ratio": "1:1"})

    generate.assert_awaited_once()
    kwargs = generate.await_args.kwargs
    assert kwargs["create_user_message"] is False
    assert kwargs["prompt"] == "watercolor fox"
    assert kwargs["aspect_ratio"] == "1:1"
    assert result.data is not None
    assert result.data["terminal"] is True
    assert result.data["image_marker"] == marker
    assert result.data["assistant_message_id"] == str(asst_id)


@pytest.mark.asyncio
async def test_invoke_surfaces_generation_error():
    adapter = ImageGenAdapter(_settings(image_generation_enabled=True))
    user = MagicMock()
    with (
        bind_image_gen_context(user=user, redis=MagicMock(), chat_id=uuid4()),
        patch(
            "app.gateways.mcp.image_gen_adapter.plan_service.is_pro",
            return_value=True,
        ),
        patch(
            "app.gateways.mcp.image_gen_adapter.image_generation_service.generate_for_chat",
            AsyncMock(side_effect=ImageGenerationError("quota", status_code=429)),
        ),
    ):
        result = await adapter.invoke({"prompt": "a cat"})
    assert "failed" in result.content.lower()
