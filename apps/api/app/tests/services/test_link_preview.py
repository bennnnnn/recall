"""Tests for app.services.link_preview with mocked HTTP and SSRF validation."""

from unittest.mock import AsyncMock, patch

import pytest

_OG_HTML = """<html><head>
<meta property="og:title" content="OG Title">
<meta property="og:description" content="OG Description">
</head></html>"""

_TITLE_HTML = "<html><head><title>Page Title</title></head></html>"

_NO_META_HTML = "<html><head></head><body>Hello</body></html>"


def _mock_response(status=200, text="", headers=None):
    m = AsyncMock()
    m.status_code = status
    m.text = text
    m.headers = headers or {}
    return m


def _setup_httpx_mock(mock_client_cls, *responses):
    """Configure the httpx.AsyncClient mock to return a sequence of responses."""
    client_instance = AsyncMock()
    client_instance.__aenter__ = AsyncMock(return_value=client_instance)
    client_instance.get = AsyncMock(side_effect=responses)
    mock_client_cls.return_value = client_instance
    return client_instance


@pytest.mark.asyncio
async def test_fetch_link_preview_returns_og_tags():
    """OG meta tags should be parsed as title and description."""
    from app.services.link_preview import fetch_link_preview

    resp = _mock_response(text=_OG_HTML)
    with (
        patch("app.services.link_preview._validate_external_url", AsyncMock()),
        patch("app.services.link_preview.httpx.AsyncClient") as mock_client,
    ):
        _setup_httpx_mock(mock_client, resp)
        result = await fetch_link_preview("https://example.com/page")

    assert result["title"] == "OG Title"
    assert result["description"] == "OG Description"
    assert result["domain"] == "example.com"


@pytest.mark.asyncio
async def test_fetch_link_preview_fallback_to_title():
    """When no OG tags exist, fall back to <title> tag."""
    from app.services.link_preview import fetch_link_preview

    resp = _mock_response(text=_TITLE_HTML)
    with (
        patch("app.services.link_preview._validate_external_url", AsyncMock()),
        patch("app.services.link_preview.httpx.AsyncClient") as mock_client,
    ):
        _setup_httpx_mock(mock_client, resp)
        result = await fetch_link_preview("https://example.com")

    assert result["title"] == "Page Title"
    assert result["description"] is None


@pytest.mark.asyncio
async def test_fetch_link_preview_handles_http_error():
    """HTTP errors should be caught and return nulls, not raised."""
    from app.services.link_preview import fetch_link_preview

    resp = _mock_response(status=500, text="Server Error")
    with (
        patch("app.services.link_preview._validate_external_url", AsyncMock()),
        patch("app.services.link_preview.httpx.AsyncClient") as mock_client,
    ):
        _setup_httpx_mock(mock_client, resp)
        result = await fetch_link_preview("https://example.com/error")

    assert result["title"] is None
    assert result["description"] is None


@pytest.mark.asyncio
async def test_fetch_link_preview_no_meta():
    """Pages with no meta or title tags should return nulls."""
    from app.services.link_preview import fetch_link_preview

    resp = _mock_response(text=_NO_META_HTML)
    with (
        patch("app.services.link_preview._validate_external_url", AsyncMock()),
        patch("app.services.link_preview.httpx.AsyncClient") as mock_client,
    ):
        _setup_httpx_mock(mock_client, resp)
        result = await fetch_link_preview("https://example.com/nometa")

    assert result["title"] is None
    assert result["description"] is None


# ── SSRF validation tests (real function, no mock) ──


@pytest.mark.asyncio
async def test_validate_external_url_blocks_loopback():
    """127.0.0.1 should be blocked as a loopback address."""
    from app.services.link_preview import _validate_external_url

    with pytest.raises(ValueError, match="Blocked request"):
        await _validate_external_url("http://127.0.0.1:8080/secret")


@pytest.mark.asyncio
async def test_validate_external_url_blocks_private_range():
    """10.x.x.x should be blocked as a private address."""
    from app.services.link_preview import _validate_external_url

    with pytest.raises(ValueError, match="Blocked request"):
        await _validate_external_url("http://10.0.0.1/admin")


@pytest.mark.asyncio
async def test_validate_external_url_blocks_link_local():
    """169.254.x.x (AWS/GCP metadata) should be blocked."""
    from app.services.link_preview import _validate_external_url

    with pytest.raises(ValueError, match="Blocked request"):
        await _validate_external_url("http://169.254.169.254/metadata")


@pytest.mark.asyncio
async def test_validate_external_url_blocks_192_168():
    """192.168.x.x should be blocked."""
    from app.services.link_preview import _validate_external_url

    with pytest.raises(ValueError, match="Blocked request"):
        await _validate_external_url("http://192.168.1.1:5432")


@pytest.mark.asyncio
async def test_validate_external_url_allows_public():
    """A public IP (e.g., 1.1.1.1) should pass validation."""
    from app.services.link_preview import _validate_external_url

    # This resolves DNS for a real public hostname; the IP check passes.
    await _validate_external_url("https://one.one.one.one/")


@pytest.mark.asyncio
async def test_validate_external_url_no_hostname():
    """A URL with no hostname should raise ValueError."""
    from app.services.link_preview import _validate_external_url

    with pytest.raises(ValueError, match="URL has no hostname"):
        await _validate_external_url("not-a-url")


# ── Redirect handling and error path tests ──


@pytest.mark.asyncio
async def test_fetch_link_preview_follows_redirect():
    """Redirect responses should be followed with re-validation of the target."""
    from app.services.link_preview import fetch_link_preview

    redirect_resp = _mock_response(status=301, headers={"Location": "https://example.com/final"})
    final_resp = _mock_response(text=_OG_HTML)

    with (
        patch("app.services.link_preview._validate_external_url", AsyncMock()),
        patch("app.services.link_preview.httpx.AsyncClient") as mock_client,
    ):
        _setup_httpx_mock(mock_client, redirect_resp, final_resp)
        result = await fetch_link_preview("https://example.com/page")

    assert result["title"] == "OG Title"
    assert result["domain"] == "example.com"


@pytest.mark.asyncio
async def test_fetch_link_preview_blocks_internal_address():
    """When _validate_external_url raises ValueError, return nulls gracefully."""
    from app.services.link_preview import fetch_link_preview

    with patch(
        "app.services.link_preview._validate_external_url",
        AsyncMock(side_effect=ValueError("Blocked request to internal/private address")),
    ):
        result = await fetch_link_preview("http://169.254.169.254/metadata")

    assert result["title"] is None
    assert result["description"] is None
    assert result["domain"] == "169.254.169.254"


@pytest.mark.asyncio
async def test_fetch_link_preview_uses_redis_cache(fake_redis):
    from app.core.config import Settings
    from app.services.link_preview import fetch_link_preview_cached

    settings = Settings(link_preview_cache_ttl=3600)
    resp = _mock_response(text=_OG_HTML)
    with (
        patch("app.services.link_preview.get_redis_client", return_value=fake_redis),
        patch("app.services.link_preview._validate_external_url", AsyncMock()),
        patch("app.services.link_preview.httpx.AsyncClient") as mock_client,
    ):
        _setup_httpx_mock(mock_client, resp)
        first = await fetch_link_preview_cached(settings, "https://example.com/page")
        second = await fetch_link_preview_cached(settings, "https://example.com/page")

    assert first["title"] == "OG Title"
    assert second == first
    assert mock_client.return_value.get.await_count == 1


@pytest.mark.asyncio
async def test_validate_external_url_unresolvable_hostname():
    """An unresolvable hostname should raise ValueError."""
    from app.services.link_preview import _validate_external_url

    with pytest.raises(ValueError, match="Cannot resolve hostname"):
        await _validate_external_url("http://thishostnamedoesnotexist.invalid/")
