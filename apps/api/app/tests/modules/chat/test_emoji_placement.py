"""Emoji follow the user's setting, whatever the model wrote (Settings → Emoji)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.modules.chat.emoji_placement import place_emoji, place_reply_emoji

# "What are the benefits of drinking water" at "A few", as the model wrote it.
_LIVE = (
    "Here are the main perks:\n\n"
    "*   **Temperature control** — water is the fuel for that system 🌡️\n"
    "*   **🧠 Brain power** — Even mild dehydration hurts focus\n"
    "*   **Kidney cleanup** — Water helps your kidneys filter waste 🚽 and flush it out.\n"
    "    - nested **Detail 🔬** point\n\n"
    "Want me to look up how much you should drink? 💧"
)


def test_a_few_moves_each_emoji_to_the_front_of_its_label() -> None:
    assert place_emoji(_LIVE, "some", user_wrote_emoji=False) == (
        "Here are the main perks:\n\n"
        "*   🌡️ **Temperature control** — water is the fuel for that system\n"
        "*   🧠 **Brain power** — Even mild dehydration hurts focus\n"
        "*   🚽 **Kidney cleanup** — Water helps your kidneys filter waste and flush it out.\n"
        "    - 🔬 nested **Detail** point\n\n"
        "Want me to look up how much you should drink?"
    )


def test_none_removes_every_emoji_and_keeps_the_layout() -> None:
    assert place_emoji(_LIVE, "off", user_wrote_emoji=False) == (
        "Here are the main perks:\n\n"
        "*   **Temperature control** — water is the fuel for that system\n"
        "*   **Brain power** — Even mild dehydration hurts focus\n"
        "*   **Kidney cleanup** — Water helps your kidneys filter waste and flush it out.\n"
        "    - nested **Detail** point\n\n"
        "Want me to look up how much you should drink?"
    )


def test_lots_keeps_them_and_none_mirrors_the_user() -> None:
    assert place_emoji(_LIVE, "more", user_wrote_emoji=False) == _LIVE
    assert place_emoji(_LIVE, "off", user_wrote_emoji=True) == _LIVE


@pytest.mark.parametrize(
    ("line", "kept"),
    [
        ("🌊 Hydration matters.", "Hydration matters."),
        ("### Singapore 🇸🇬", "### 🇸🇬 Singapore"),
        ("**Low taxes 💰** — Singapore", "💰 **Low taxes** — Singapore"),
        ("> Note: drink up 💧", "> Note: drink up"),
        ("1. **Sleep** — rest well 😴.", "1. 😴 **Sleep** — rest well."),
        ("- 💧 **Water** — and more 🚰", "- 💧 **Water** — and more"),
    ],
)
def test_a_few_lines(line: str, kept: str) -> None:
    assert place_emoji(line, "some", user_wrote_emoji=False) == kept


@pytest.mark.parametrize(
    "text",
    [
        # Fences (the clarify card's options), inline code, table rows and lessons.
        '```clarify\n{"options": ["💰 Money", "🌿 Life"]}\n```',
        'Use `print("🐍")` to print it.',
        "| Country | Tax |\n|---|---|\n| UAE ✅ | 0% |",
        "### Lesson 1: Lists 🐍\n\nCorrect! 🎉 A list holds items.",
        "No emoji here.",
    ],
)
def test_what_a_few_leaves_alone(text: str) -> None:
    assert place_emoji(text, "some", user_wrote_emoji=False) == text


def _state(text: str, level: str | None, *, said: str = "hi", server: bool = False) -> Any:
    user = SimpleNamespace(emoji_use=level) if level else None
    ctx = SimpleNamespace(user=user, user_message_content=said)
    return cast(Any, SimpleNamespace(text=text, ctx=ctx, server_text=server))


def test_the_pass_reads_the_users_setting_and_message() -> None:
    line = "🌊 Hydration matters."
    assert place_reply_emoji(_state(line, "some")) == "Hydration matters."
    assert place_reply_emoji(_state(line, "off", said="hey 👋")) == line
    # Server text, or no user to read a setting from, is left as it is.
    assert place_reply_emoji(_state(line, "off", server=True)) == line
    assert place_reply_emoji(_state(line, None)) == line


# Every case the phone's twin (features/chat/model/emojiPlacement.ts) reads too: the
# streaming draft is already the reply that will be saved.
_CASES = json.loads(
    (
        Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "emoji_placement_cases.json"
    ).read_text()
)


@pytest.mark.parametrize("case", _CASES, ids=[case["name"] for case in _CASES])
def test_the_shared_cases(case: dict[str, Any]) -> None:
    placed = place_emoji(case["text"], case["level"], user_wrote_emoji=case["user_wrote_emoji"])
    assert placed == case["expected"]
