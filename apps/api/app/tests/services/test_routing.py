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
        # Smart triggers → smart-chat
        ("explain quantum computing", "smart-chat"),
        ("why is the sky blue", "smart-chat"),
        ("prove p = np", "smart-chat"),
        ("analyze this algorithm", "smart-chat"),
        ("debug the memory leak", "smart-chat"),
        ("compare two architectures", "smart-chat"),
        ("design a distributed queue", "smart-chat"),
        ("evaluate this approach", "smart-chat"),
        ("derive the formula", "smart-chat"),
        ("refactor this module", "smart-chat"),
        ("step by step how to deploy", "smart-chat"),
        ("reason about this design", "smart-chat"),
        ("optimize this query", "smart-chat"),
        ("trade-off between latency and throughput", "smart-chat"),
        ("what is the complexity of this", "smart-chat"),
        # Long message (>500 chars → smart-chat)
        ("a" * 501, "smart-chat"),
        # At boundary: exactly 500 chars → smart-chat (>= trigger)
        ("a" * 500, "smart-chat"),
        # Just under boundary: 499 chars → free-chat
        ("a" * 499, "free-chat"),
        # Code block → smart-chat
        ("check this out:\n```\nprint(1)\n```", "smart-chat"),
    ],
)
def test_route_chat_model(content: str, expected: str) -> None:
    assert route_chat_model(content) == expected


def test_is_reasoning_alias() -> None:
    from app.services.model_catalog import is_reasoning_alias

    assert is_reasoning_alias("smart-chat") is True
    assert is_reasoning_alias("max-chat") is True
    assert is_reasoning_alias("free-chat") is False


@pytest.mark.parametrize(
    "alias,content,expected",
    [
        # auto resolves via route_chat_model
        ("auto", "hello", "free-chat"),
        ("auto", "explain gravity", "smart-chat"),
        # explicit aliases pass through
        ("free-chat", "explain gravity", "free-chat"),
        ("smart-chat", "hi", "smart-chat"),
        ("max-chat", "anything", "max-chat"),
    ],
)
def test_resolve_alias(alias: str, content: str, expected: str) -> None:
    assert resolve_alias(alias, content) == expected
