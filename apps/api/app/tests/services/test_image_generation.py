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
        image_generation_model="black-forest-labs/flux.2-klein-4b",
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


def _mock_http_client(**kwargs):
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    for name, value in kwargs.items():
        setattr(client, name, value)
    return client


@pytest.mark.asyncio
async def test_generate_image_openrouter_url_response_is_fetched_ssrf_safely():
    """When OpenRouter returns a `url` instead of b64_json, the image bytes must be
    fetched through the shared SSRF-safe helper (DNS-pinned), not a plain GET."""
    settings = Settings(
        openrouter_api_key="test-key",
        image_generation_enabled=True,
        image_generation_model="black-forest-labs/flux.2-klein-4b",
    )
    payload = {"data": [{"url": "https://cdn.example.com/out.png"}]}
    post_response = MagicMock()
    post_response.status_code = 200
    post_response.json.return_value = payload
    post_response.raise_for_status = MagicMock()
    post_client = _mock_http_client(post=AsyncMock(return_value=post_response))

    png = b"\x89PNG\r\n\x1a\n"
    get_response = MagicMock()
    get_response.status_code = 200
    get_response.headers = {"content-type": "image/png"}
    get_response.content = png
    get_response.raise_for_status = MagicMock()
    get_client = _mock_http_client(get=AsyncMock(return_value=get_response))

    with (
        patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=False),
        patch(
            "app.gateways.image_gateway.httpx.AsyncClient",
            side_effect=[post_client, get_client],
        ),
        patch(
            "app.gateways.safe_fetch.resolve_external_host",
            AsyncMock(return_value=("cdn.example.com", "93.184.216.34")),
        ),
    ):
        result = await generate_image(settings, prompt="sunset over mountains")

    assert result == (png, "image/png")
    call = get_client.get.await_args
    # The request must go out to the pinned IP, not the raw hostname.
    assert call.args[0] == "https://93.184.216.34/out.png"
    assert call.kwargs["headers"]["Host"] == "cdn.example.com"


@pytest.mark.asyncio
async def test_generate_image_openrouter_b64_json_rejects_oversized_payload():
    """BUG FIX: every other attachment path enforces MAX_ATTACHMENT_SIZE.
    A provider response bigger than that cap must be rejected, not written
    straight through to storage."""
    from app.services.attachment_content import MAX_ATTACHMENT_SIZE

    settings = Settings(
        openrouter_api_key="test-key",
        image_generation_enabled=True,
        image_generation_model="black-forest-labs/flux.2-klein-4b",
    )
    import base64

    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * MAX_ATTACHMENT_SIZE
    payload = {"data": [{"b64_json": base64.b64encode(oversized).decode("ascii")}]}
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
        result = await generate_image(settings, prompt="sunset over mountains")

    assert result is None


@pytest.mark.asyncio
async def test_generate_image_openrouter_url_response_rejects_oversized_payload():
    """Same size cap applied to the URL-fetch branch."""
    from app.services.attachment_content import MAX_ATTACHMENT_SIZE

    settings = Settings(
        openrouter_api_key="test-key",
        image_generation_enabled=True,
        image_generation_model="black-forest-labs/flux.2-klein-4b",
    )
    payload = {"data": [{"url": "https://cdn.example.com/out.png"}]}
    post_response = MagicMock()
    post_response.status_code = 200
    post_response.json.return_value = payload
    post_response.raise_for_status = MagicMock()
    post_client = _mock_http_client(post=AsyncMock(return_value=post_response))

    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * MAX_ATTACHMENT_SIZE
    get_response = MagicMock()
    get_response.status_code = 200
    get_response.headers = {"content-type": "image/png"}
    get_response.content = oversized
    get_response.raise_for_status = MagicMock()
    get_client = _mock_http_client(get=AsyncMock(return_value=get_response))

    with (
        patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=False),
        patch(
            "app.gateways.image_gateway.httpx.AsyncClient",
            side_effect=[post_client, get_client],
        ),
        patch(
            "app.gateways.safe_fetch.resolve_external_host",
            AsyncMock(return_value=("cdn.example.com", "93.184.216.34")),
        ),
    ):
        result = await generate_image(settings, prompt="sunset over mountains")

    assert result is None


@pytest.mark.asyncio
async def test_generate_image_openrouter_url_response_normalizes_content_type_casing():
    """A CDN returning a mixed-case Content-Type (valid per HTTP, case-
    insensitive by spec) must not break downstream signature matching."""
    settings = Settings(
        openrouter_api_key="test-key",
        image_generation_enabled=True,
        image_generation_model="black-forest-labs/flux.2-klein-4b",
    )
    payload = {"data": [{"url": "https://cdn.example.com/out.png"}]}
    post_response = MagicMock()
    post_response.status_code = 200
    post_response.json.return_value = payload
    post_response.raise_for_status = MagicMock()
    post_client = _mock_http_client(post=AsyncMock(return_value=post_response))

    png = b"\x89PNG\r\n\x1a\n"
    get_response = MagicMock()
    get_response.status_code = 200
    get_response.headers = {"content-type": "Image/PNG; charset=binary"}
    get_response.content = png
    get_response.raise_for_status = MagicMock()
    get_client = _mock_http_client(get=AsyncMock(return_value=get_response))

    with (
        patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=False),
        patch(
            "app.gateways.image_gateway.httpx.AsyncClient",
            side_effect=[post_client, get_client],
        ),
        patch(
            "app.gateways.safe_fetch.resolve_external_host",
            AsyncMock(return_value=("cdn.example.com", "93.184.216.34")),
        ),
    ):
        result = await generate_image(settings, prompt="sunset over mountains")

    assert result == (png, "image/png")


@pytest.mark.asyncio
async def test_generate_image_openrouter_url_response_blocks_private_ip():
    """A provider-returned URL pointing at an internal address must be rejected,
    not fetched."""
    settings = Settings(
        openrouter_api_key="test-key",
        image_generation_enabled=True,
        image_generation_model="black-forest-labs/flux.2-klein-4b",
    )
    payload = {"data": [{"url": "http://169.254.169.254/latest/meta-data/"}]}
    post_response = MagicMock()
    post_response.status_code = 200
    post_response.json.return_value = payload
    post_response.raise_for_status = MagicMock()
    post_client = _mock_http_client(post=AsyncMock(return_value=post_response))

    with (
        patch("app.services.image_generation.mock_llm.should_mock_llm", return_value=False),
        patch("app.gateways.image_gateway.httpx.AsyncClient", return_value=post_client),
    ):
        result = await generate_image(settings, prompt="sunset over mountains")

    assert result is None
