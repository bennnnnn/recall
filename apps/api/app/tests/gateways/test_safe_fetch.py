"""Tests for the shared SSRF-safe fetch helpers in app.gateways.safe_fetch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateways import safe_fetch


def _mock_response(status=200, headers=None):
    m = MagicMock()
    m.status_code = status
    m.headers = headers or {}
    return m


# ── resolve_external_host / validate_external_url (real function, no mock) ──


@pytest.mark.asyncio
async def test_resolve_external_host_blocks_loopback():
    with pytest.raises(ValueError, match="Blocked request"):
        await safe_fetch.resolve_external_host("http://127.0.0.1:8080/secret")


@pytest.mark.asyncio
async def test_resolve_external_host_blocks_private_range():
    with pytest.raises(ValueError, match="Blocked request"):
        await safe_fetch.resolve_external_host("http://10.0.0.1/admin")


@pytest.mark.asyncio
async def test_resolve_external_host_blocks_cgnat():
    with pytest.raises(ValueError, match=safe_fetch.PRIVATE_IP_ERR):
        await safe_fetch.resolve_external_host("http://100.64.1.1/admin")


@pytest.mark.asyncio
async def test_resolve_external_host_blocks_link_local():
    """169.254.x.x (AWS/GCP metadata) should be blocked."""
    with pytest.raises(ValueError, match="Blocked request"):
        await safe_fetch.resolve_external_host("http://169.254.169.254/metadata")


@pytest.mark.asyncio
async def test_resolve_external_host_literal_public_ip():
    hostname, ip = await safe_fetch.resolve_external_host("http://93.184.216.34/x")
    assert hostname == "93.184.216.34"
    assert ip == "93.184.216.34"


@pytest.mark.asyncio
async def test_validate_external_url_no_hostname():
    with pytest.raises(ValueError, match="URL has no hostname"):
        await safe_fetch.validate_external_url("http:///no-host")


# ── pin_url / host_header ──────────────────────────────────────────────────


def test_pin_url_formats_ipv4_and_ipv6():
    assert safe_fetch.pin_url("https://example.com/a?b=1", "1.2.3.4") == "https://1.2.3.4/a?b=1"
    assert safe_fetch.pin_url("https://example.com:8443/a", "1.2.3.4") == "https://1.2.3.4:8443/a"
    assert safe_fetch.pin_url("https://example.com/a", "2001:db8::1") == "https://[2001:db8::1]/a"


def test_host_header_omits_default_ports():
    assert safe_fetch.host_header("example.com", 443, "https") == "example.com"
    assert safe_fetch.host_header("example.com", 80, "http") == "example.com"
    assert safe_fetch.host_header("example.com", 8443, "https") == "example.com:8443"


# ── get_pinned / fetch_safely (mocked client + resolve) ─────────────────────


@pytest.mark.asyncio
async def test_get_pinned_pins_ip_and_sets_host_header():
    resolve_mock = AsyncMock(return_value=("example.com", "93.184.216.34"))
    client = AsyncMock()
    client.get = AsyncMock(return_value=_mock_response())
    with patch("app.gateways.safe_fetch.resolve_external_host", resolve_mock):
        await safe_fetch.get_pinned(client, "https://example.com/page", headers={"User-Agent": "x"})

    call = client.get.await_args
    assert call.args[0] == "https://93.184.216.34/page"
    assert call.kwargs["headers"]["Host"] == "example.com"
    assert call.kwargs["headers"]["User-Agent"] == "x"
    assert call.kwargs["extensions"] == {"sni_hostname": "example.com"}


@pytest.mark.asyncio
async def test_fetch_safely_follows_redirect_and_revalidates():
    """Each redirect hop must be re-resolved/re-pinned, not just followed blindly."""
    resolve_mock = AsyncMock(return_value=("example.com", "93.184.216.34"))
    redirect_resp = _mock_response(status=302, headers={"Location": "https://example.com/final"})
    final_resp = _mock_response(status=200)
    client = AsyncMock()
    client.get = AsyncMock(side_effect=[redirect_resp, final_resp])
    with patch("app.gateways.safe_fetch.resolve_external_host", resolve_mock):
        resp = await safe_fetch.fetch_safely(client, "https://example.com/start")

    assert resp is final_resp
    assert resolve_mock.await_count == 2
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_fetch_safely_stops_after_max_redirects():
    resolve_mock = AsyncMock(return_value=("example.com", "93.184.216.34"))
    redirect_resp = _mock_response(status=302, headers={"Location": "https://example.com/loop"})
    client = AsyncMock()
    client.get = AsyncMock(return_value=redirect_resp)
    with patch("app.gateways.safe_fetch.resolve_external_host", resolve_mock):
        resp = await safe_fetch.fetch_safely(client, "https://example.com/start", max_redirects=2)

    assert resp is redirect_resp
    assert client.get.await_count == 3  # initial + 2 redirect hops


@pytest.mark.asyncio
async def test_fetch_safely_blocks_redirect_to_private_ip():
    """A redirect that targets an internal address must be rejected, not followed."""
    redirect_resp = _mock_response(
        status=302, headers={"Location": "http://169.254.169.254/metadata"}
    )
    resolve_mock = AsyncMock(
        side_effect=[
            ("example.com", "93.184.216.34"),
            ValueError(safe_fetch.PRIVATE_IP_ERR),
        ]
    )
    client = AsyncMock()
    client.get = AsyncMock(return_value=redirect_resp)
    with patch("app.gateways.safe_fetch.resolve_external_host", resolve_mock):
        with pytest.raises(ValueError, match="Blocked request"):
            await safe_fetch.fetch_safely(client, "https://example.com/start")

    assert client.get.await_count == 1


@pytest.mark.asyncio
async def test_read_stream_capped_stops_after_max_bytes():
    class _Stream:
        def __init__(self) -> None:
            self.chunks = [b"abcd", b"efgh", b"ijkl"]

        def aiter_bytes(self):
            async def _gen():
                for chunk in self.chunks:
                    yield chunk

            return _gen()

    body = await safe_fetch.read_stream_capped(_Stream(), max_body_bytes=6)
    assert body == b"abcdef"
    assert len(body) == 6


@pytest.mark.asyncio
async def test_get_pinned_streams_when_max_body_bytes_set():
    resolve_mock = AsyncMock(return_value=("example.com", "93.184.216.34"))
    stream_resp = MagicMock()
    stream_resp.status_code = 200
    stream_resp.headers = {"content-type": "text/html"}
    stream_resp.request = MagicMock()

    async def aiter_bytes():
        yield b"x" * 100
        yield b"y" * 100

    stream_resp.aiter_bytes = aiter_bytes

    class _StreamCtx:
        async def __aenter__(self):
            return stream_resp

        async def __aexit__(self, *args):
            return None

    client = MagicMock()
    client.stream = MagicMock(return_value=_StreamCtx())
    client.get = AsyncMock()

    with patch("app.gateways.safe_fetch.resolve_external_host", resolve_mock):
        resp = await safe_fetch.get_pinned(client, "https://example.com/huge", max_body_bytes=50)

    client.get.assert_not_awaited()
    assert len(resp.content) == 50
    assert resp.content == b"x" * 50
