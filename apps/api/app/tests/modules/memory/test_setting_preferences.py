"""A preference an app setting decides is not memory.

"Reply in Spanish from now on" was saved as "User prefers replies in Spanish and without
emojis", and a lesson turn answered an English app in Spanish (2026-10-24). Reading facts
with patterns hid real ones ("User answers customer emails in Spanish at work"), so the
memory models are told instead, and the reply's language line ranks a saved memory last.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm
from app.modules.chat.response_tone import EMOJI_HINTS
from app.modules.memory import llm as memory_llm
from app.modules.memory.llm import INSTRUCT_SETTING_RULE, SETTING_PREFERENCE_RULE


async def _system_prompt(monkeypatch: pytest.MonkeyPatch, call: Any) -> str:
    captured: dict[str, Any] = {}

    async def fake_complete_structured(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mock_llm, "should_mock_llm", lambda _settings: False)
    monkeypatch.setattr(litellm_gateway, "complete_structured", fake_complete_structured)
    await call()
    return str(captured["messages"][0]["content"])


@pytest.mark.asyncio
async def test_extraction_leaves_a_settings_preference_to_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = await _system_prompt(
        monkeypatch,
        lambda: memory_llm.revise_memory_facts(Settings(), "User: reply in Spanish from now on"),
    )
    assert SETTING_PREFERENCE_RULE in system


@pytest.mark.asyncio
async def test_the_memory_page_points_a_settings_preference_to_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = await _system_prompt(
        monkeypatch,
        lambda: memory_llm.instruct_memory(
            Settings(), "Always reply to me in Spanish", existing_facts=[], existing_areas=[]
        ),
    )
    assert INSTRUCT_SETTING_RULE in system


@pytest.mark.parametrize("level", list(EMOJI_HINTS))
def test_the_emoji_setting_outranks_a_saved_memory(level: str) -> None:
    assert EMOJI_HINTS[level].endswith("a saved memory never changes it.")
