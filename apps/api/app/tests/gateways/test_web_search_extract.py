"""Tavily extract_pages: batch page fetch for job posting text."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.gateways import web_search_gateway
from app.gateways.web_search_gateway import extract_pages


def _settings(**overrides: Any) -> MagicMock:
    settings = MagicMock(
        web_search_enabled=True,
        tavily_api_key="test-key",
    )
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _client_responding(payload: dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    return client


async def test_extract_pages_returns_trimmed_text_keyed_by_url() -> None:
    client = _client_responding(
        {
            "results": [
                {"url": "https://jobs.example.com/1", "raw_content": "  Hello   world  "},
                {"url": "https://jobs.example.com/2", "raw_content": ""},
            ],
            "failed_results": [{"url": "https://jobs.example.com/3"}],
        }
    )
    with patch.object(web_search_gateway, "get_pooled_client", return_value=client):
        pages = await extract_pages(
            _settings(),
            ["https://jobs.example.com/1", "https://jobs.example.com/2"],
        )
    assert pages == {"https://jobs.example.com/1": "Hello world"}


async def test_extract_pages_caps_page_length() -> None:
    client = _client_responding(
        {"results": [{"url": "https://jobs.example.com/1", "raw_content": "x" * 9000}]}
    )
    with patch.object(web_search_gateway, "get_pooled_client", return_value=client):
        pages = await extract_pages(_settings(), ["https://jobs.example.com/1"])
    assert len(pages["https://jobs.example.com/1"]) == web_search_gateway.EXTRACT_MAX_CHARS


async def test_extract_pages_degrades_to_empty_on_http_failure() -> None:
    client = MagicMock()
    client.post = AsyncMock(side_effect=RuntimeError("boom"))
    with patch.object(web_search_gateway, "get_pooled_client", return_value=client):
        pages = await extract_pages(_settings(), ["https://jobs.example.com/1"])
    assert pages == {}


async def test_extract_pages_skips_call_when_unconfigured() -> None:
    settings = _settings(tavily_api_key="")
    with patch.object(
        web_search_gateway, "get_pooled_client", side_effect=AssertionError("no call")
    ):
        assert await extract_pages(settings, ["https://jobs.example.com/1"]) == {}
    assert await extract_pages(_settings(), []) == {}
