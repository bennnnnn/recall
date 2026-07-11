"""Tests for app.services.image_generation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.image_generation import generate_image, normalize_aspect_ratio


def test_normalize_aspect_ratio():
    assert normalize_aspect_ratio("16:9") == "16:9"
    assert normalize_aspect_ratio(" 1:1 ") == "1:1"
    assert normalize_aspect_ratio("2:1") is None
    assert normalize_aspect_ratio(None) is None


@pytest.mark.asyncio
async def test_generate_image_returns_mock_png():
    settings = Settings(mock_llm_enabled=True, image_generation_enabled=True)
    with patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=True):
        result = await generate_image(settings, prompt="a red cat")
    assert result is not None
    data, content_type = result
    assert content_type == "image/png"
    assert data.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_generate_image_disabled_returns_none():
    settings = Settings(image_generation_enabled=False)
    assert await generate_image(settings, prompt="hello") is None


@pytest.mark.asyncio
async def test_generate_image_rejects_empty_prompt():
    settings = Settings(mock_llm_enabled=True, image_generation_enabled=True)
    with patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=True):
        assert await generate_image(settings, prompt="   ") is None


@pytest.mark.asyncio
async def test_generate_image_openrouter_b64_json():
    settings = Settings(
        openrouter_api_key="test-key",
        image_generation_enabled=True,
        image_generation_model="black-forest-labs/flux-schnell",
    )
    import base64

    png = b"\x89PNG\r\n\x1a\n"
    payload = {"data": [{"b64_json": base64.b64encode(png).decode("ascii")}]}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=False),
        patch("app.gateways.image_gateway.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await generate_image(settings, prompt="sunset over mountains", aspect_ratio="16:9")

    assert result == (png, "image/png")
    call_json = mock_client.post.await_args.kwargs["json"]
    assert call_json["aspect_ratio"] == "16:9"
