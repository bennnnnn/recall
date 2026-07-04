"""Tests for Expo push gateway."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.gateways import expo_push_gateway as gateway


@pytest.mark.asyncio
async def test_send_push_messages_empty_returns_no_failures():
    result = await gateway.send_push_messages([])
    assert result.invalid_tokens == []
    assert result.delivered == []


@pytest.mark.asyncio
async def test_send_push_messages_prunes_invalid_tokens():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "data": [
            {"status": "ok", "id": "ticket-1"},
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

    with (
        patch("app.gateways.expo_push_gateway.httpx.AsyncClient", return_value=client),
        patch(
            "app.gateways.expo_push_gateway.fetch_push_receipts",
            AsyncMock(
                return_value={
                    "ticket-1": {"status": "ok"},
                }
            ),
        ),
        patch("app.gateways.expo_push_gateway.asyncio.sleep", AsyncMock()),
    ):
        result = await gateway.send_push_messages(
            [{"to": "ExponentPushToken[aaa]"}, {"to": "ExponentPushToken[bbb]"}]
        )

    assert result.invalid_tokens == ["ExponentPushToken[bbb]"]
    assert result.delivered == [True, False]


@pytest.mark.asyncio
async def test_send_push_messages_waits_for_receipt_before_marking_delivered():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"data": [{"status": "ok", "id": "ticket-1"}]}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.gateways.expo_push_gateway.httpx.AsyncClient", return_value=client),
        patch(
            "app.gateways.expo_push_gateway.fetch_push_receipts",
            AsyncMock(return_value={"ticket-1": {"status": "ok"}}),
        ) as receipts_mock,
        patch("app.gateways.expo_push_gateway.asyncio.sleep", AsyncMock()) as sleep_mock,
    ):
        result = await gateway.send_push_messages([{"to": "ExponentPushToken[aaa]"}])

    sleep_mock.assert_awaited_once()
    receipts_mock.assert_awaited_once_with(["ticket-1"])
    assert result.delivered == [True]


@pytest.mark.asyncio
async def test_send_push_messages_leaves_pending_receipts_undelivered():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"data": [{"status": "ok", "id": "ticket-1"}]}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.gateways.expo_push_gateway.httpx.AsyncClient", return_value=client),
        patch(
            "app.gateways.expo_push_gateway.fetch_push_receipts",
            AsyncMock(return_value={"ticket-1": {"status": "pending"}}),
        ),
        patch("app.gateways.expo_push_gateway.asyncio.sleep", AsyncMock()),
    ):
        result = await gateway.send_push_messages([{"to": "ExponentPushToken[aaa]"}])

    assert result.delivered == [False]


@pytest.mark.asyncio
async def test_fetch_push_receipts_batches_requests():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "data": {
            "ticket-1": {"status": "ok"},
            "ticket-2": {"status": "ok"},
        }
    }
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.gateways.expo_push_gateway.httpx.AsyncClient", return_value=client):
        receipts = await gateway.fetch_push_receipts(["ticket-1", "ticket-2"])

    assert receipts["ticket-1"]["status"] == "ok"
    assert receipts["ticket-2"]["status"] == "ok"


@pytest.mark.asyncio
async def test_send_push_messages_network_error_returns_empty():
    client = AsyncMock()
    client.post = AsyncMock(side_effect=httpx.HTTPError("boom"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.gateways.expo_push_gateway.httpx.AsyncClient", return_value=client):
        result = await gateway.send_push_messages([{"to": "ExponentPushToken[x]"}])

    assert result.invalid_tokens == []
    assert result.delivered == [False]
