"""Tests for the Gmail message fetch fan-out (partial failure isolation)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways import google_gmail_gateway as gw


def _list_response(ids: list[str]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"messages": [{"id": mid} for mid in ids]}
    return resp


def _detail_response(msg_id: str, subject: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "id": msg_id,
        "snippet": "snippet",
        "labelIds": [],
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "Subject", "value": subject}],
            "body": {},
        },
    }
    return resp


@pytest.mark.asyncio
async def test_list_recent_messages_isolates_per_message_failures():
    """BUG FIX regression: one failing message detail fetch must not discard
    every other successfully-fetched message in the same batch — mirrors
    how list_upcoming_events already isolates per-calendar failures."""
    settings = Settings(gmail_enabled=True, google_client_id="x", google_client_secret="y")
    ids = ["ok-1", "fail", "ok-2"]

    async def fake_get(url, params=None, headers=None):
        if url == gw.GMAIL_MESSAGES_URL:
            return _list_response(ids)
        msg_id = url.rsplit("/", 1)[-1]
        if msg_id == "fail":
            raise RuntimeError("boom")
        return _detail_response(msg_id, f"Subject {msg_id}")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=fake_get)

    with (
        patch.object(gw, "_access_token", AsyncMock(return_value="token")),
        patch.object(gw, "get_pooled_client", return_value=mock_client),
    ):
        messages = await gw.list_recent_messages(settings, "refresh-token")

    assert {m.id for m in messages} == {"ok-1", "ok-2"}


@pytest.mark.asyncio
async def test_list_recent_messages_all_succeed():
    settings = Settings(gmail_enabled=True, google_client_id="x", google_client_secret="y")
    ids = ["a", "b", "c"]

    async def fake_get(url, params=None, headers=None):
        if url == gw.GMAIL_MESSAGES_URL:
            return _list_response(ids)
        msg_id = url.rsplit("/", 1)[-1]
        return _detail_response(msg_id, f"Subject {msg_id}")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=fake_get)

    with (
        patch.object(gw, "_access_token", AsyncMock(return_value="token")),
        patch.object(gw, "get_pooled_client", return_value=mock_client),
    ):
        messages = await gw.list_recent_messages(settings, "refresh-token")

    assert {m.id for m in messages} == {"a", "b", "c"}
