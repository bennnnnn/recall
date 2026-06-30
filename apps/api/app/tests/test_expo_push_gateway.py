"""Tests for Expo push gateway."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.gateways import expo_push_gateway as gateway


@pytest.mark.asyncio
async def test_send_push_messages_empty_returns_no_failures():
    assert await gateway.send_push_messages([]) == []


@pytest.mark.asyncio
async def test_send_push_messages_prunes_invalid_tokens():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "data": [
            {"status": "ok"},
            {
                "status": "error",
                "details": {"error": "DeviceNotRegistered"},
            },
        ]
    }
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.gateways.expo_push_gateway.httpx.AsyncClient", return_value=client):
        failed = await gateway.send_push_messages(
            [{"to": "ExponentPushToken[aaa]"}, {"to": "ExponentPushToken[bbb]"}]
        )

    assert failed == ["ExponentPushToken[bbb]"]


@pytest.mark.asyncio
async def test_send_push_messages_network_error_returns_empty():
    client = AsyncMock()
    client.post = AsyncMock(side_effect=httpx.HTTPError("boom"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.gateways.expo_push_gateway.httpx.AsyncClient", return_value=client):
        failed = await gateway.send_push_messages([{"to": "ExponentPushToken[x]"}])

    assert failed == []
