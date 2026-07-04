"""Tests for app.services.routing — pure functions, no I/O needed."""

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
        # Tagged code fence → smart-chat; bare fence → free-chat
        ("check this:\n```python\nprint(1)\n```", "smart-chat"),
        ("check this out:\n```\nprint(1)\n```", "free-chat"),
    ],
)
def test_route_chat_model(content: str, expected: str) -> None:
    assert route_chat_model(content) == expected


def test_is_reasoning_alias() -> None:
    from app.services.model_catalog import is_reasoning_alias, quota_multiplier

    assert is_reasoning_alias("smart-chat") is True
    assert is_reasoning_alias("max-chat") is True
    assert is_reasoning_alias("free-chat") is False
    assert quota_multiplier("free-chat") == 1.0
    assert quota_multiplier("smart-chat") == 3.5
    assert quota_multiplier("max-chat") == 3.5


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
