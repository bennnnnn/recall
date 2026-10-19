"""The model is told Recall searches and shows photos, and the classifier sees the reply."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.models.schemas import WebSearchClassification
from app.modules.chat.prompt_constants import PHOTO_LOOKUP_HINT
from app.modules.chat.prompt_sections import _integration_hints
from app.modules.web_search import WEB_SEARCH_HINT


def _awaited(mock: AsyncMock) -> Any:
    """The last await of *mock*; fails the test when it was never awaited."""
    assert mock.await_args is not None
    return mock.await_args


def _hints(**settings) -> str:
    parts = _integration_hints(
        settings=Settings(**settings),
        query_text="Show me her image",
        local_tz="UTC",
        user_locale="en",
        location_for_context=None,
        prompt_location=None,
        memory_block="",
        attachment_rag_block="",
        todos_section=None,
    )
    return "\n".join(parts)


def test_search_hint_forbids_claiming_no_browsing() -> None:
    assert "never say you can't browse" in WEB_SEARCH_HINT
    assert WEB_SEARCH_HINT in _hints(web_search_enabled=True)


def test_photo_hint_follows_the_photo_lookup_flag() -> None:
    assert "Never say you can't display, show or send images" in PHOTO_LOOKUP_HINT
    assert PHOTO_LOOKUP_HINT in _hints(image_search_enabled=True)
    assert PHOTO_LOOKUP_HINT not in _hints(image_search_enabled=False)


@pytest.mark.asyncio
async def test_classifier_reads_the_last_reply() -> None:
    from app.modules.web_search.classify import classify_web_search_need

    complete = AsyncMock(
        return_value=WebSearchClassification(needs_search=True, query="Jeanne Calment death")
    )
    with (
        patch(
            "app.modules.web_search.classify.quota_service.global_spend_exceeded",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.web_search.classify.quota_service.record_global_spend",
            AsyncMock(),
        ),
        patch("app.modules.web_search.classify.litellm_gateway.complete_structured", complete),
        patch("app.modules.web_search.classify.get_redis_client", return_value=AsyncMock()),
    ):
        await classify_web_search_need(
            Settings(mock_llm_enabled=False, web_search_classifier_enabled=True),
            "when did she die?",
            prior_user_messages=["Who lived the longest?"],
            prior_assistant="Jeanne Calment, who reached 122 years.",
        )

    prompt = _awaited(complete).kwargs["messages"][1]["content"]
    assert "Assistant's last reply:\nJeanne Calment, who reached 122 years." in prompt
