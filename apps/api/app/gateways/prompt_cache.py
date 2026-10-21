"""Where a provider may cache a chat prompt, for the models that cache only a marked prefix.

A chat prompt opens with two system messages (``modules/chat/prompt_builder``): the
stable one, the same text on every turn of this kind for this user, then this turn's
own context. Most providers reuse an identical prefix by themselves. A model flagged
``cache_breakpoints`` (Anthropic's) caches only up to a ``cache_control`` mark, so its
stable message goes as one text part carrying the mark: OpenRouter's format, which
LiteLLM forwards for Claude.
"""

from __future__ import annotations

from typing import Any

from app.models.model_catalog import ChatModel

# The cache lifetime every caching provider offers; it renews on each hit.
EPHEMERAL = {"type": "ephemeral"}


def with_cache_breakpoint(messages: list[dict[str, Any]], route: ChatModel) -> list[dict[str, Any]]:
    """``messages`` with the stable system message marked, when ``route`` needs the mark.

    Only a stable message followed by the turn's own system message is marked: a lone
    system prompt holds that turn's text too, and a mark on it would pay a cache write
    on every turn and never be read. The messages are not changed in place.
    """
    if not route.cache_breakpoints or len(messages) < 2:
        return messages
    stable, turn = messages[0], messages[1]
    text = stable.get("content")
    if stable.get("role") != "system" or turn.get("role") != "system":
        return messages
    if not isinstance(text, str) or not text:
        return messages
    part = {"type": "text", "text": text, "cache_control": dict(EPHEMERAL)}
    return [{**stable, "content": [part]}, *messages[1:]]
