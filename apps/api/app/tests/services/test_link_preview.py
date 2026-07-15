"""Tests for app.services.link_preview with mocked HTTP and SSRF validation.

The fetch path now routes through ``app.gateways.safe_fetch.fetch_safely``;
the SSRF-safe DNS pinning + per-hop re-validation is exercised in
``test_safe_fetch.py``. Here we patch ``fetch_safely`` so we can assert the
service calls it with the right URL + UA and parses its response, without
re-testing fetch_safely's internals.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_OG_HTML = """<html><head>
<meta property="og:title" content="OG Title">
<meta property="og:description" content="OG Description">
</head></html>"""

_TITLE_HTML = "<html><head><title>Page Title</title></head></html>"

_NO_META_HTML = "<html><head></head><body>Hello</body></html>"


def _mock_response(status=200, text="", headers=None):
    m = MagicMock()
    m.status_code = status
    m.text = text
    m.headers = headers or {}
    return m


def _fetch_safely_patch(response):
    """Patch link_preview.fetch_safely to return *response*."""
    return patch(
        "app.services.link_preview.fetch_safely",
        AsyncMock(return_value=response),
    )


@pytest.mark.asyncio
async def test_fetch_link_preview_returns_og_tags():
    """OG meta tags should be parsed as title and description."""
    from app.services.link_preview import fetch_link_preview

    resp = _mock_response(text=_OG_HTML)
    with _fetch_safely_patch(resp) as fetch_mock:
        result = await fetch_link_preview("https://example.com/page")

    assert result["title"] == "OG Title"
    assert result["description"] == "OG Description"
    assert result["domain"] == "example.com"
    fetch_mock.assert_awaited_once()
    # Service must pass the URL through to fetch_safely (SSRF-safe fetch).
    assert fetch_mock.await_args.args[1] == "https://example.com/page"
    # And send the link-preview User-Agent.
    assert fetch_mock.await_args.kwargs["headers"]["User-Agent"].startswith("RecallLinkPreview")


@pytest.mark.asyncio
async def test_fetch_link_preview_fallback_to_title():
    """When no OG tags exist, fall back to <title> tag."""
    from app.services.link_preview import fetch_link_preview

    resp = _mock_response(text=_TITLE_HTML)
    with _fetch_safely_patch(resp):
        result = await fetch_link_preview("https://example.com")

    assert result["title"] == "Page Title"
    assert result["description"] is None


@pytest.mark.asyncio
async def test_fetch_link_preview_handles_http_error():
    """HTTP errors should be caught and return nulls, not raised."""
    from app.services.link_preview import fetch_link_preview

    resp = _mock_response(status=500, text="Server Error")
    with _fetch_safely_patch(resp):
        result = await fetch_link_preview("https://example.com/error")

    assert result["title"] is None
    assert result["description"] is None


@pytest.mark.asyncio
async def test_fetch_link_preview_no_meta():
    """Pages with no meta or title tags should return nulls."""
    from app.services.link_preview import fetch_link_preview

    resp = _mock_response(text=_NO_META_HTML)
    with _fetch_safely_patch(resp):
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
        await _validate_external_url("http:///no-host")


@pytest.mark.asyncio
async def test_pin_url_formats_ipv4_and_ipv6():
    # pin_url lives in safe_fetch now; link_preview delegates to it.
    from app.gateways.safe_fetch import pin_url

    assert pin_url("https://example.com/a?b=1", "1.2.3.4") == "https://1.2.3.4/a?b=1"
    assert pin_url("https://example.com:8443/a", "1.2.3.4") == "https://1.2.3.4:8443/a"
    assert pin_url("https://example.com/a", "2001:db8::1") == "https://[2001:db8::1]/a"


# ── Redirect handling and error path tests ──


@pytest.mark.asyncio
async def test_fetch_link_preview_follows_redirect():
    """Redirects are handled inside fetch_safely; link_preview just parses the final body."""
    from app.services.link_preview import fetch_link_preview

    final_resp = _mock_response(text=_OG_HTML)
    with _fetch_safely_patch(final_resp):
        result = await fetch_link_preview("https://example.com/page")

    assert result["title"] == "OG Title"
    assert result["domain"] == "example.com"


@pytest.mark.asyncio
async def test_fetch_link_preview_blocks_internal_address():
    """When fetch_safely raises ValueError (blocked internal address), return nulls gracefully."""
    from app.services.link_preview import fetch_link_preview

    with patch(
        "app.services.link_preview.fetch_safely",
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
        _fetch_safely_patch(resp) as fetch_mock,
    ):
        first = await fetch_link_preview_cached(settings, "https://example.com/page")
        second = await fetch_link_preview_cached(settings, "https://example.com/page")

    assert first["title"] == "OG Title"
    assert second == first
    # Second call hits the cache; fetch_safely is only called once.
    assert fetch_mock.await_count == 1


@pytest.mark.asyncio
async def test_validate_external_url_unresolvable_hostname():
    """An unresolvable hostname should raise ValueError."""
    from app.services.link_preview import _validate_external_url

    with pytest.raises(ValueError, match="Cannot resolve hostname"):
        await _validate_external_url("http://thishostnamedoesnotexist.invalid/")
