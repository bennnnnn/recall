"""Integration: math tools wired into chat augment path."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.services.chat import _augment_web_and_tools


@pytest.mark.asyncio
async def test_augment_web_and_tools_injects_math_for_solve() -> None:
    settings = Settings(mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True)
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "Solve x^2 + 2 = 6"},
    ]

    with patch(
        "app.services.chat.web_search_service.augment_prompt_messages",
        AsyncMock(return_value=(messages, [])),
    ):
        updated, hits = await _augment_web_and_tools(
            messages,
            "Solve x^2 + 2 = 6",
            settings,
        )

    assert hits == []
    assert len(updated) == 3
    assert updated[1]["role"] == "system"
    assert "SymPy" in updated[1]["content"]
    assert "Solutions" in updated[1]["content"]
