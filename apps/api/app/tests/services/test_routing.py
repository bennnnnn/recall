"""Tests for app.services.routing — pure functions, no I/O needed."""

import time

import pytest

from app.services.routing import resolve_alias, route_chat_model


@pytest.mark.parametrize(
    "content,expected",
    [
        # Simple messages → free-chat
        ("hi", "free-chat"),
        ("hello world", "free-chat"),
        ("what's for lunch", "free-chat"),
        ("explain quantum computing", "free-chat"),
        ("why is the sky blue", "free-chat"),
        ("compare two options", "free-chat"),
        # Smart triggers → smart-chat
        ("prove p = np", "smart-chat"),
        ("debug the memory leak", "smart-chat"),
        ("analyze this algorithm", "smart-chat"),
        ("design a distributed queue", "smart-chat"),
        ("derive the formula", "smart-chat"),
        ("refactor this module", "smart-chat"),
        ("step by step how to deploy", "smart-chat"),
        ("optimize this query", "smart-chat"),
        ("trade-off between latency and throughput", "smart-chat"),
        ("what is the complexity of this", "smart-chat"),
        # Long message (>=800 chars → smart-chat)
        ("a" * 801, "smart-chat"),
        ("a" * 799, "free-chat"),
        # Any code fence → smart-chat, regardless of language tag (or lack of
        # one). BUG FIX: this used to only match a fixed language allowlist,
        # so a bare fence or an unlisted language (bash, shell, C, HTML, ...)
        # silently stayed on free-chat even with real pasted code.
        ("check this:\n```python\nprint(1)\n```", "smart-chat"),
        ("check this out:\n```\nprint(1)\n```", "smart-chat"),
        ("run this:\n```bash\necho hi\n```", "smart-chat"),
        ("what's wrong here:\n```html\n<div></div>\n```", "smart-chat"),
    ],
)
def test_route_chat_model(content: str, expected: str) -> None:
    assert route_chat_model(content) == expected


def test_code_fence_detection_is_linear_time_not_quadratic():
    """SECURITY FIX (CodeQL: polynomial regex on uncontrolled data). The
    first version's fence pattern used `\\s*` for leading whitespace, which
    overlaps with what `(?:^|\\n)` already matches — a message that's mostly
    newlines with no closing fence let the engine retry the same run of
    `\\n`s from every line-start position, going quadratic in input length.
    A user-controlled chat message hitting this path is exactly "uncontrolled
    data" — a large adversarial input here must stay fast, not blow up.

    Exercises the compiled pattern directly (not through route_chat_model)
    since route_chat_model short-circuits on the separate long-message
    length check well before an adversarial 200k-char input would ever
    reach the fence regex.
    """
    from app.services.routing import _CODE_FENCE

    # No closing fence anywhere — the worst case for a backtracking engine
    # that overlaps whitespace-skipping with the newline it already matched.
    adversarial = "\n" * 200_000
    started = time.perf_counter()
    _CODE_FENCE.search(adversarial)
    elapsed = time.perf_counter() - started
    # Generous ceiling for a slow CI runner; a quadratic implementation on
    # 200k newlines would take many seconds to minutes, not under a second.
    assert elapsed < 2.0


def test_is_reasoning_alias() -> None:
    from app.services.model_catalog import is_reasoning_alias, quota_multiplier

    assert is_reasoning_alias("smart-chat") is True
    assert is_reasoning_alias("max-chat") is True
    assert is_reasoning_alias("free-chat") is False
    assert quota_multiplier("free-chat") == 1.0
    assert quota_multiplier("smart-chat") == 3.5
    assert quota_multiplier("max-chat") == 3.5


def test_weighted_reserve_tokens_applies_quota_multiplier() -> None:
    from unittest.mock import patch

    from app.core.config import Settings
    from app.services.chat.stream import weighted_reserve_tokens

    settings = Settings()
    with patch("app.services.chat.stream.estimate_tokens", return_value=100):
        free = weighted_reserve_tokens(
            content="hello",
            model="free-chat",
            settings=settings,
            max_output=50,
        )
        smart = weighted_reserve_tokens(
            content="hello",
            model="smart-chat",
            settings=settings,
            max_output=50,
        )
    assert free == 150
    assert smart == 525


@pytest.mark.parametrize(
    "alias,content,expected",
    [
        # auto resolves via route_chat_model
        ("auto", "hello", "free-chat"),
        ("auto", "explain gravity", "free-chat"),
        ("auto", "debug this crash", "smart-chat"),
        # explicit aliases pass through
        ("free-chat", "explain gravity", "free-chat"),
        ("smart-chat", "hi", "smart-chat"),
        ("max-chat", "anything", "max-chat"),
    ],
)
def test_resolve_alias(alias: str, content: str, expected: str) -> None:
    assert resolve_alias(alias, content) == expected
