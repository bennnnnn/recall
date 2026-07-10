from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateways.pronunciation_lookup import lookup_pronunciation_url


@pytest.mark.asyncio
async def test_lookup_pronunciation_url_returns_https_audio():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"phonetics": [{"audio": "https://cdn.example.com/apple.mp3"}]},
    ]
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    with patch(
        "app.gateways.pronunciation_lookup.get_pooled_client",
        return_value=mock_client,
    ):
        url = await lookup_pronunciation_url("apple")
    assert url == "https://cdn.example.com/apple.mp3"


@pytest.mark.asyncio
async def test_lookup_pronunciation_url_skips_phrases():
    assert await lookup_pronunciation_url("ice cream") is None
