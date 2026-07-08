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
async def test_generate_image_openrouter_b64_json_mislabeled_jpeg():
    settings = Settings(
        openrouter_api_key="test-key",
        image_generation_enabled=True,
        image_generation_model="bytedance-seed/seedream-4.5",
    )
    import base64

    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    payload = {
        "data": [
            {
                "b64_json": base64.b64encode(jpeg).decode("ascii"),
                "media_type": "image/png",
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=False),
        patch("app.services.image_generation.list_provider_slugs", AsyncMock(return_value=[])),
        patch("app.services.image_generation.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await generate_image(settings, prompt="a cat")

    assert result == (jpeg, "image/jpeg")


@pytest.mark.asyncio
async def test_generate_image_openrouter_b64_json():
    settings = Settings(
        openrouter_api_key="test-key",
        image_generation_enabled=True,
        image_generation_model="google/gemini-2.5-flash-image",
    )
    import base64

    png = b"\x89PNG\r\n\x1a\n"
    payload = {"data": [{"b64_json": base64.b64encode(png).decode("ascii")}]}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=False),
        patch("app.services.image_generation.list_provider_slugs", AsyncMock(return_value=[])),
        patch("app.services.image_generation.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await generate_image(settings, prompt="sunset over mountains", aspect_ratio="16:9")

    assert result == (png, "image/png")
    call_json = mock_client.post.await_args.kwargs["json"]
    assert call_json["aspect_ratio"] == "16:9"
    headers = mock_client.post.await_args.kwargs["headers"]
    assert headers["HTTP-Referer"]
    assert headers["X-Title"] == "Recall"


@pytest.mark.asyncio
async def test_generate_image_falls_back_to_second_model():
    settings = Settings(
        openrouter_api_key="test-key",
        image_generation_enabled=True,
        image_generation_model="vendor/primary-image",
        image_generation_fallback_models="vendor/fallback-image",
    )
    import base64

    png = b"\x89PNG\r\n\x1a\n"
    ok_payload = {"data": [{"b64_json": base64.b64encode(png).decode("ascii")}]}
    fail_response = MagicMock()
    fail_response.status_code = 502
    fail_response.text = "provider error"
    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.json.return_value = ok_payload

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[fail_response, ok_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=False),
        patch("app.services.image_generation.list_provider_slugs", AsyncMock(return_value=[])),
        patch("app.services.image_generation.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await generate_image(settings, prompt="a cat")

    assert result == (png, "image/png")
    assert mock_client.post.await_count == 2
    models = [call.kwargs["json"]["model"] for call in mock_client.post.await_args_list]
    assert models == ["vendor/primary-image", "vendor/fallback-image"]


def test_image_model_candidates_dedupes_primary():
    settings = Settings(
        image_generation_model="bytedance-seed/seedream-4.5",
        image_generation_fallback_models="bytedance-seed/seedream-4.5,google/gemini-2.5-flash-image",
    )
    from app.services.image_generation import image_model_candidates

    assert image_model_candidates(settings) == [
        "bytedance-seed/seedream-4.5",
        "google/gemini-2.5-flash-image",
    ]
